"""
Multi-Modal Text Processing Pipeline
Handles text, image, audio, and video data processing for WMS categorization.
"""

import asyncio
import base64
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib

# Media processing
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import speech_recognition as sr
from moviepy.editor import VideoFileClip
import pytesseract

# NLP processing  
import spacy
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain_openai import AzureChatOpenAI

from ..core.config import get_azure_openai_settings
from ..core.logging import LoggerMixin
from ..core.llm_constraints import get_constraint_validator
from ..database.vector_store import get_weaviate_manager


class MediaType(Enum):
    """Types of media input"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


class ProcessingStage(Enum):
    """Processing stages"""
    INTAKE = "intake"
    EXTRACTION = "extraction"
    CLASSIFICATION = "classification"
    CATEGORIZATION = "categorization"
    STORAGE = "storage"
    COMPLETE = "complete"


@dataclass
class MediaContent:
    """Represents processed media content"""
    content_id: str
    media_type: MediaType
    raw_content: Any
    extracted_text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    categories: List[str] = field(default_factory=list)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    processing_stage: ProcessingStage = ProcessingStage.INTAKE
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None


@dataclass
class ProcessingResult:
    """Result of processing pipeline"""
    success: bool
    content: Optional[MediaContent]
    wms_categories: List[str] = field(default_factory=list)
    extracted_entities: Dict[str, List[str]] = field(default_factory=dict)
    confidence: float = 0.0
    processing_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class MultiModalTextProcessor(LoggerMixin):
    """Main text processing pipeline for multi-modal data"""
    
    def __init__(self):
        super().__init__()
        self.nlp = self._load_nlp_model()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        self.llm = self._initialize_llm()
        self.constraint_validator = get_constraint_validator()
        self.vector_manager = get_weaviate_manager()
        
        # WMS category mappings
        self.wms_categories = {
            'locations': {
                'keywords': ['location', 'bin', 'aisle', 'zone', 'coordinate', 'warehouse', 'dock'],
                'entities': ['location_id', 'bin_number', 'zone_code']
            },
            'items': {
                'keywords': ['item', 'product', 'sku', 'part', 'material', 'catalog'],
                'entities': ['item_id', 'sku', 'part_number']
            },
            'inventory': {
                'keywords': ['inventory', 'stock', 'quantity', 'balance', 'count'],
                'entities': ['quantity', 'stock_level', 'inventory_id']
            },
            'receiving': {
                'keywords': ['receive', 'receipt', 'inbound', 'asn', 'delivery'],
                'entities': ['receipt_id', 'asn_number', 'po_number']
            },
            'work': {
                'keywords': ['work', 'task', 'assignment', 'labor', 'productivity'],
                'entities': ['task_id', 'work_order', 'assignment_id']
            },
            'shipping': {
                'keywords': ['ship', 'outbound', 'carrier', 'freight', 'delivery'],
                'entities': ['shipment_id', 'tracking_number', 'carrier_code']
            },
            'picking': {
                'keywords': ['pick', 'order', 'fulfillment', 'wave'],
                'entities': ['order_id', 'pick_list', 'wave_id']
            },
            'packing': {
                'keywords': ['pack', 'carton', 'container', 'box'],
                'entities': ['carton_id', 'container_number']
            }
        }
    
    def _load_nlp_model(self):
        """Load spaCy NLP model"""
        try:
            return spacy.load("en_core_web_sm")
        except OSError:
            self.log_warning("spaCy model not found. Install with: python -m spacy download en_core_web_sm")
            return None
    
    def _initialize_llm(self) -> AzureChatOpenAI:
        """Initialize Azure OpenAI for processing"""
        azure_settings = get_azure_openai_settings()
        
        return AzureChatOpenAI(
            azure_deployment=azure_settings.deployment_chat,
            openai_api_version=azure_settings.api_version,
            azure_endpoint=str(azure_settings.endpoint),
            api_key=azure_settings.api_key,
            temperature=0.1,
            max_tokens=2000
        )
    
    async def process_content(self, content: Any, media_type: MediaType,
                            user_context: Dict[str, Any] = None) -> ProcessingResult:
        """Main processing pipeline for any media type"""
        start_time = datetime.utcnow()
        
        try:
            # Create content object
            content_id = self._generate_content_id(content, media_type)
            media_content = MediaContent(
                content_id=content_id,
                media_type=media_type,
                raw_content=content,
                processing_stage=ProcessingStage.INTAKE
            )
            
            self.log_info(f"Processing {media_type.value} content", content_id=content_id)
            
            # Stage 1: Extract text from media
            media_content = await self._extract_text(media_content)
            
            # Stage 2: Process and analyze text
            media_content = await self._analyze_text(media_content)
            
            # Stage 3: Categorize into WMS categories
            media_content = await self._categorize_content(media_content)
            
            # Stage 4: Extract entities
            entities = await self._extract_entities(media_content)
            
            # Stage 5: Validate with constraints
            validation_result = await self._validate_processing(media_content, user_context)
            
            # Stage 6: Store processed content
            if validation_result['is_valid']:
                await self._store_content(media_content)
                media_content.processing_stage = ProcessingStage.COMPLETE
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return ProcessingResult(
                success=validation_result['is_valid'],
                content=media_content,
                wms_categories=media_content.categories,
                extracted_entities=entities,
                confidence=media_content.confidence_scores.get('overall', 0.0),
                processing_time=processing_time,
                errors=[v.description for v in validation_result.get('violations', []) 
                       if v.severity in ['critical', 'high']],
                warnings=[v.description for v in validation_result.get('violations', [])
                         if v.severity in ['medium', 'low']]
            )
            
        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self.log_error(f"Processing failed: {e}")
            
            return ProcessingResult(
                success=False,
                content=None,
                processing_time=processing_time,
                errors=[str(e)]
            )
    
    async def _extract_text(self, content: MediaContent) -> MediaContent:
        """Extract text from different media types"""
        content.processing_stage = ProcessingStage.EXTRACTION
        
        try:
            if content.media_type == MediaType.TEXT:
                content.extracted_text = str(content.raw_content)
            
            elif content.media_type == MediaType.IMAGE:
                content.extracted_text = await self._extract_text_from_image(content.raw_content)
            
            elif content.media_type == MediaType.AUDIO:
                content.extracted_text = await self._extract_text_from_audio(content.raw_content)
            
            elif content.media_type == MediaType.VIDEO:
                content.extracted_text = await self._extract_text_from_video(content.raw_content)
            
            elif content.media_type == MediaType.DOCUMENT:
                content.extracted_text = await self._extract_text_from_document(content.raw_content)
            
            content.metadata['extraction_length'] = len(content.extracted_text)
            self.log_info(f"Extracted {len(content.extracted_text)} characters from {content.media_type.value}")
            
        except Exception as e:
            self.log_error(f"Text extraction failed: {e}")
            content.extracted_text = ""
            content.metadata['extraction_error'] = str(e)
        
        return content
    
    async def _extract_text_from_image(self, image_data: Any) -> str:
        """Extract text from images using OCR"""
        try:
            # Handle different image input types
            if isinstance(image_data, str):
                # Base64 encoded image
                if image_data.startswith('data:image'):
                    image_data = image_data.split(',')[1]
                image_bytes = base64.b64decode(image_data)
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    tmp_file.write(image_bytes)
                    tmp_path = tmp_file.name
                
                # Open with PIL
                image = Image.open(tmp_path)
            
            elif isinstance(image_data, bytes):
                # Raw bytes
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    tmp_file.write(image_data)
                    tmp_path = tmp_file.name
                
                image = Image.open(tmp_path)
            
            else:
                # Assume PIL Image or file path
                image = Image.open(image_data) if isinstance(image_data, str) else image_data
            
            # Preprocess image for better OCR
            image = self._preprocess_image_for_ocr(image)
            
            # Extract text using Tesseract
            extracted_text = pytesseract.image_to_string(image, config='--psm 6')
            
            # Clean up temporary file if created
            if 'tmp_path' in locals():
                Path(tmp_path).unlink(missing_ok=True)
            
            return extracted_text.strip()
            
        except Exception as e:
            self.log_error(f"Image OCR failed: {e}")
            return ""
    
    async def _extract_text_from_audio(self, audio_data: Any) -> str:
        """Extract text from audio using speech recognition"""
        try:
            recognizer = sr.Recognizer()
            
            # Handle different audio input types
            if isinstance(audio_data, str):
                # File path
                with sr.AudioFile(audio_data) as source:
                    audio = recognizer.record(source)
            
            elif isinstance(audio_data, bytes):
                # Raw audio bytes - save to temp file
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                    tmp_file.write(audio_data)
                    tmp_path = tmp_file.name
                
                with sr.AudioFile(tmp_path) as source:
                    audio = recognizer.record(source)
                
                Path(tmp_path).unlink(missing_ok=True)
            
            else:
                audio = audio_data
            
            # Use Google Web Speech API for recognition
            try:
                text = recognizer.recognize_google(audio)
                return text
            except sr.RequestError:
                # Fallback to offline recognition
                try:
                    text = recognizer.recognize_sphinx(audio)
                    return text
                except:
                    return ""
            
        except Exception as e:
            self.log_error(f"Audio transcription failed: {e}")
            return ""
    
    async def _extract_text_from_video(self, video_data: Any) -> str:
        """Extract text from video (audio track + frame OCR)"""
        try:
            # Save video to temporary file if needed
            if isinstance(video_data, bytes):
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
                    tmp_file.write(video_data)
                    video_path = tmp_file.name
            else:
                video_path = video_data
            
            extracted_texts = []
            
            # Extract audio and transcribe
            try:
                clip = VideoFileClip(video_path)
                
                # Extract audio
                if clip.audio:
                    audio_path = video_path.replace('.mp4', '_audio.wav')
                    clip.audio.write_audiofile(audio_path, verbose=False, logger=None)
                    
                    audio_text = await self._extract_text_from_audio(audio_path)
                    if audio_text:
                        extracted_texts.append(f"Audio: {audio_text}")
                    
                    Path(audio_path).unlink(missing_ok=True)
                
                # Extract text from key frames
                duration = clip.duration
                frame_count = min(10, int(duration))  # Sample max 10 frames
                
                for i in range(frame_count):
                    timestamp = i * (duration / frame_count)
                    frame = clip.get_frame(timestamp)
                    
                    # Convert to PIL Image
                    frame_image = Image.fromarray(frame.astype('uint8'), 'RGB')
                    
                    # Extract text from frame
                    frame_text = await self._extract_text_from_image(frame_image)
                    if frame_text and len(frame_text) > 10:  # Only meaningful text
                        extracted_texts.append(f"Frame {i}: {frame_text}")
                
                clip.close()
                
            except Exception as e:
                self.log_warning(f"Video processing error: {e}")
            
            # Clean up temporary file
            if isinstance(video_data, bytes):
                Path(video_path).unlink(missing_ok=True)
            
            return "\n".join(extracted_texts)
            
        except Exception as e:
            self.log_error(f"Video text extraction failed: {e}")
            return ""
    
    async def _extract_text_from_document(self, doc_data: Any) -> str:
        """Extract text from documents (PDF, Word, etc.)"""
        try:
            # This would use libraries like PyPDF2, python-docx, etc.
            # Simplified implementation
            if isinstance(doc_data, str):
                # Assume it's already text content
                return doc_data
            
            # For now, return empty string for actual document processing
            # In production, implement proper document parsing
            return ""
            
        except Exception as e:
            self.log_error(f"Document text extraction failed: {e}")
            return ""
    
    def _preprocess_image_for_ocr(self, image: Image.Image) -> Image.Image:
        """Preprocess image to improve OCR accuracy"""
        try:
            # Convert to grayscale
            if image.mode != 'L':
                image = image.convert('L')
            
            # Convert to numpy array for OpenCV processing
            img_array = np.array(image)
            
            # Apply image processing for better OCR
            # Noise reduction
            img_array = cv2.medianBlur(img_array, 3)
            
            # Contrast enhancement
            img_array = cv2.convertScaleAbs(img_array, alpha=1.2, beta=20)
            
            # Thresholding for better text detection
            _, img_array = cv2.threshold(img_array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Convert back to PIL Image
            return Image.fromarray(img_array)
            
        except Exception as e:
            self.log_warning(f"Image preprocessing failed: {e}")
            return image
    
    async def _analyze_text(self, content: MediaContent) -> MediaContent:
        """Analyze extracted text for structure and content"""
        content.processing_stage = ProcessingStage.CLASSIFICATION
        
        if not content.extracted_text:
            return content
        
        try:
            # NLP analysis with spaCy
            if self.nlp:
                doc = self.nlp(content.extracted_text)
                
                # Extract named entities
                entities = {}
                for ent in doc.ents:
                    if ent.label_ not in entities:
                        entities[ent.label_] = []
                    entities[ent.label_].append(ent.text)
                
                content.metadata['nlp_entities'] = entities
                content.metadata['sentence_count'] = len(list(doc.sents))
                content.metadata['token_count'] = len(doc)
            
            # Language detection and text quality assessment
            content.metadata.update(await self._assess_text_quality(content.extracted_text))
            
            self.log_info(f"Text analysis complete for {content.content_id}")
            
        except Exception as e:
            self.log_error(f"Text analysis failed: {e}")
            content.metadata['analysis_error'] = str(e)
        
        return content
    
    async def _assess_text_quality(self, text: str) -> Dict[str, Any]:
        """Assess quality and characteristics of extracted text"""
        quality_metrics = {
            'length': len(text),
            'word_count': len(text.split()),
            'avg_word_length': np.mean([len(word) for word in text.split()]) if text.split() else 0,
            'contains_numbers': bool(re.search(r'\d', text)),
            'contains_punctuation': bool(re.search(r'[.,!?;:]', text)),
            'uppercase_ratio': sum(c.isupper() for c in text) / len(text) if text else 0,
            'quality_score': 0.0
        }
        
        # Calculate quality score
        score = 0.0
        if quality_metrics['length'] > 10:
            score += 0.3
        if quality_metrics['word_count'] > 3:
            score += 0.3
        if quality_metrics['contains_punctuation']:
            score += 0.2
        if 0.1 < quality_metrics['uppercase_ratio'] < 0.9:  # Mixed case is good
            score += 0.2
        
        quality_metrics['quality_score'] = score
        
        return quality_metrics
    
    async def _categorize_content(self, content: MediaContent) -> MediaContent:
        """Categorize content into WMS categories"""
        content.processing_stage = ProcessingStage.CATEGORIZATION
        
        if not content.extracted_text:
            return content
        
        try:
            text_lower = content.extracted_text.lower()
            categories = []
            confidence_scores = {}
            
            # Keyword-based categorization
            for category, config in self.wms_categories.items():
                score = 0.0
                matches = 0
                
                # Check keywords
                for keyword in config['keywords']:
                    if keyword in text_lower:
                        matches += 1
                        score += 1.0
                
                # Bonus for multiple matches
                if matches > 1:
                    score *= 1.2
                
                # Normalize score
                score = min(1.0, score / len(config['keywords']))
                
                if score > 0.3:  # Threshold for category inclusion
                    categories.append(category)
                    confidence_scores[category] = score
            
            # LLM-based categorization for complex content
            if len(categories) == 0 or max(confidence_scores.values()) < 0.5:
                llm_categories = await self._llm_categorize(content.extracted_text)
                categories.extend(llm_categories)
            
            # Default to 'other' if no categories found
            if not categories:
                categories = ['other_data_categorization']
                confidence_scores['other_data_categorization'] = 0.5
            
            content.categories = categories
            content.confidence_scores = confidence_scores
            content.confidence_scores['overall'] = max(confidence_scores.values()) if confidence_scores else 0.0
            
            self.log_info(f"Categorized as: {categories}", content_id=content.content_id)
            
        except Exception as e:
            self.log_error(f"Categorization failed: {e}")
            content.categories = ['other_data_categorization']
            content.confidence_scores = {'other_data_categorization': 0.5, 'overall': 0.5}
        
        return content
    
    async def _llm_categorize(self, text: str) -> List[str]:
        """Use LLM for advanced categorization"""
        try:
            category_list = ', '.join(self.wms_categories.keys())
            
            prompt = f"""
            Analyze the following text and categorize it into WMS (Warehouse Management System) categories.
            
            Available categories: {category_list}
            
            Text to categorize:
            {text[:1000]}  # Limit text length
            
            Return only the most relevant category names as a comma-separated list.
            If uncertain, return 'other_data_categorization'.
            """
            
            response = await self.llm.ainvoke(prompt)
            
            # Parse response
            categories = []
            for cat in response.content.split(','):
                cat = cat.strip().lower()
                if cat in self.wms_categories:
                    categories.append(cat)
            
            return categories if categories else ['other_data_categorization']
            
        except Exception as e:
            self.log_error(f"LLM categorization failed: {e}")
            return ['other_data_categorization']
    
    async def _extract_entities(self, content: MediaContent) -> Dict[str, List[str]]:
        """Extract WMS-specific entities from content"""
        entities = {}
        
        if not content.extracted_text:
            return entities
        
        text = content.extracted_text
        
        # Pattern-based entity extraction
        entity_patterns = {
            'order_id': [r'order[_\s]*(?:id|number)[_\s]*:?\s*([A-Z0-9]+)', r'order[_\s]+([A-Z0-9]{6,})'],
            'item_id': [r'item[_\s]*(?:id|number)[_\s]*:?\s*([A-Z0-9]+)', r'sku[_\s]*:?\s*([A-Z0-9]+)'],
            'location_id': [r'location[_\s]*(?:id|number)[_\s]*:?\s*([A-Z0-9]+)', r'bin[_\s]*:?\s*([A-Z0-9]+)'],
            'quantity': [r'(?:quantity|qty|count)[_\s]*:?\s*(\d+(?:\.\d+)?)', r'(\d+(?:\.\d+)?)\s*(?:units|pieces|pcs)'],
            'date': [r'(\d{4}-\d{2}-\d{2})', r'(\d{1,2}/\d{1,2}/\d{4})'],
            'user_id': [r'user[_\s]*(?:id|number)[_\s]*:?\s*([A-Z0-9]+)', r'employee[_\s]*:?\s*([A-Z0-9]+)']
        }
        
        for entity_type, patterns in entity_patterns.items():
            matches = []
            for pattern in patterns:
                found = re.findall(pattern, text, re.IGNORECASE)
                matches.extend(found)
            
            if matches:
                entities[entity_type] = list(set(matches))  # Remove duplicates
        
        return entities
    
    async def _validate_processing(self, content: MediaContent, 
                                 user_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate processed content using constraint system"""
        try:
            # Prepare validation context
            validation_context = {
                'content_type': content.media_type.value,
                'categories': content.categories,
                'confidence': content.confidence_scores.get('overall', 0.0),
                'user_role': user_context.get('user_role', 'end_user') if user_context else 'end_user'
            }
            
            # Validate the extracted text and categorization
            result = await self.constraint_validator.validate_response(
                response=content.extracted_text,
                context=validation_context
            )
            
            return result
            
        except Exception as e:
            self.log_error(f"Validation failed: {e}")
            return {'is_valid': True, 'violations': []}  # Allow processing to continue
    
    async def _store_content(self, content: MediaContent):
        """Store processed content in vector database"""
        try:
            # Prepare document for vector storage
            document = {
                'id': content.content_id,
                'content_type': content.media_type.value,
                'extracted_text': content.extracted_text,
                'categories': json.dumps(content.categories),
                'confidence_scores': json.dumps(content.confidence_scores),
                'metadata': json.dumps(content.metadata),
                'processed_at': content.processed_at.isoformat() if content.processed_at else datetime.utcnow().isoformat()
            }
            
            # Store in vector database
            success = await self.vector_manager.store_documents(
                documents=[document],
                class_name="ProcessedContent"
            )
            
            if success:
                content.processing_stage = ProcessingStage.STORAGE
                self.log_info(f"Content stored successfully", content_id=content.content_id)
            else:
                self.log_error(f"Failed to store content", content_id=content.content_id)
            
        except Exception as e:
            self.log_error(f"Content storage failed: {e}")
    
    def _generate_content_id(self, content: Any, media_type: MediaType) -> str:
        """Generate unique content ID"""
        content_str = str(content)[:1000]  # Limit for hashing
        timestamp = datetime.utcnow().isoformat()
        
        hash_input = f"{media_type.value}:{content_str}:{timestamp}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    async def search_processed_content(self, query: str, categories: List[str] = None,
                                     limit: int = 10) -> List[Dict[str, Any]]:
        """Search processed content"""
        try:
            # Add category filter if specified
            where_filter = {}
            if categories:
                where_filter = {
                    "path": ["categories"],
                    "operator": "ContainsAny",
                    "valueText": categories
                }
            
            results = await self.vector_manager.search_knowledge(
                query=query,
                class_name="ProcessedContent",
                limit=limit,
                where_filter=where_filter if categories else None
            )
            
            # Format results
            formatted_results = []
            for result in results:
                data = result.get('data', {})
                formatted_results.append({
                    'content_id': data.get('id'),
                    'content_type': data.get('content_type'),
                    'extracted_text': data.get('extracted_text', '')[:500],  # Preview
                    'categories': json.loads(data.get('categories', '[]')),
                    'confidence': json.loads(data.get('confidence_scores', '{}')),
                    'certainty': result.get('certainty', 0.0)
                })
            
            return formatted_results
            
        except Exception as e:
            self.log_error(f"Content search failed: {e}")
            return []


# Global instance
_text_processor: Optional[MultiModalTextProcessor] = None


def get_text_processor() -> MultiModalTextProcessor:
    """Get or create global text processor instance"""
    global _text_processor
    
    if _text_processor is None:
        _text_processor = MultiModalTextProcessor()
    
    return _text_processor


async def process_user_content(content: Any, media_type: str, 
                             user_context: Dict[str, Any] = None) -> ProcessingResult:
    """Convenience function to process user content"""
    processor = get_text_processor()
    media_type_enum = MediaType(media_type.lower())
    
    return await processor.process_content(content, media_type_enum, user_context)