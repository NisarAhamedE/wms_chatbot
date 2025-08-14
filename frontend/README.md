# WMS Chatbot Frontend

A comprehensive React TypeScript frontend application for the WMS Chatbot system with file management capabilities.

## Features

### 🔐 Authentication
- Secure login with JWT tokens
- User profile management
- Session management
- Demo credentials: `demo` / `demo123`

### 📊 Dashboard
- Real-time processing statistics
- File upload/processing overview
- Quick action buttons
- Recent activity feed
- System health monitoring

### 📁 File Management
- **Multi-modal Upload**: Documents, Images, Audio, Video
- **WMS Categorization**: 16 categories aligned with WMS functionality
- **Drag & Drop Interface**: Intuitive file upload
- **Processing Pipeline**: Real-time file processing status
- **Search & Filter**: Advanced file discovery
- **Bulk Operations**: Process multiple files at once
- **Export Capabilities**: Multiple format support

### 🤖 Intelligent Chatbot
- **80 Specialized Agents**: 5 agents per WMS category
- **Context-Aware**: File-based conversations
- **Session Management**: Multiple chat sessions
- **Agent Selection**: Choose specific WMS experts
- **Message History**: Persistent conversations
- **File Integration**: Reference uploaded documents

### 🗄️ Database Management
- **Multi-Database Support**: PostgreSQL, SQL Server, MySQL
- **Schema Explorer**: Browse database structure
- **Query Builder**: Visual and SQL interfaces
- **Query History**: Track executed queries
- **Sample Queries**: Pre-built WMS queries
- **Connection Management**: Secure database connections

## Technology Stack

### Core
- **React 18** - Modern React with hooks
- **TypeScript** - Type-safe development
- **Material-UI 5** - Enterprise-grade components
- **Redux Toolkit** - State management
- **RTK Query** - API integration

### Features
- **React Router** - Client-side routing
- **React Dropzone** - File upload functionality
- **Recharts** - Data visualization
- **Date-fns** - Date manipulation

## Project Structure

```
src/
├── components/          # Reusable UI components
│   ├── common/         # Common components (LoadingSpinner, ErrorBoundary)
│   └── layout/         # Layout components (NavigationLayout)
├── pages/              # Page components
│   ├── LoginPage.tsx
│   ├── DashboardPage.tsx
│   ├── FileManagementPage.tsx
│   ├── ChatbotPage.tsx
│   └── DatabaseManagementPage.tsx
├── store/              # Redux store configuration
│   └── slices/         # Redux slices
├── services/           # API services (RTK Query)
├── theme/              # Material-UI theme configuration
└── types/              # TypeScript type definitions
```

## WMS Categories

The system supports 16 specialized WMS categories:

1. **Wave Management** - Wave planning and release strategies
2. **Allocation** - Inventory allocation and reservations
3. **Locating and Putaway** - Storage location management
4. **Picking** - Order picking operations
5. **Cycle Counting** - Inventory accuracy management
6. **Replenishment** - Stock replenishment strategies
7. **Labor Management** - Workforce optimization
8. **Yard Management** - Dock and yard operations
9. **Slotting** - Optimal product placement
10. **Cross-Docking** - Direct transfer operations
11. **Returns Management** - Return processing
12. **Inventory Management** - Stock level monitoring
13. **Order Management** - Order lifecycle management
14. **Task Management** - Work task coordination
15. **Reports and Analytics** - Business intelligence
16. **Other** - General WMS functionality

## API Integration

The frontend integrates with a FastAPI backend through RTK Query services:

- **Authentication API** - User management and security
- **Files API** - File upload, processing, and management
- **Chat API** - Chatbot sessions and messages
- **Database API** - Database connections and queries

## Development

### Prerequisites
- Node.js 16+
- npm or yarn

### Setup
1. Install dependencies:
   ```bash
   npm install --legacy-peer-deps
   ```

2. Configure environment:
   ```bash
   cp .env.example .env
   ```

3. Start development server:
   ```bash
   npm start
   ```

### Available Scripts
- `npm start` - Start development server
- `npm build` - Build production bundle
- `npm test` - Run tests
- `npm run lint` - Check code quality
- `npm run typecheck` - TypeScript validation

## Configuration

### Environment Variables
```env
REACT_APP_API_URL=http://localhost:5000/api
REACT_APP_WEBSOCKET_URL=ws://localhost:5000/ws
```

### API Proxy
The development server proxies API requests to `http://localhost:5000`.

## Deployment

### Production Build
```bash
npm run build
```

### Docker Deployment
```dockerfile
FROM node:16-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --legacy-peer-deps
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

## Features in Detail

### File Processing Pipeline
1. **Upload** - Multi-file drag & drop with category selection
2. **Validation** - File type and size validation
3. **Processing** - Text extraction, categorization, summarization
4. **Vectorization** - Semantic search preparation
5. **Storage** - Dual database storage (PostgreSQL + Weaviate)

### Chatbot Intelligence
- **Category-Specific Agents**: Each WMS category has specialized agents
- **Context Integration**: Chat with uploaded file context
- **Multi-Session Support**: Separate conversations per topic
- **Response Quality**: Confidence scoring and source tracking

### Database Integration
- **Operational Database**: Connect to existing WMS databases
- **Safe Querying**: Row limits and timeout protection
- **Schema Exploration**: Browse tables and relationships
- **Query Templates**: Pre-built WMS-specific queries

## Security

- **JWT Authentication** - Secure token-based auth
- **Role-Based Access** - User permission management
- **Input Validation** - Client and server-side validation
- **Error Boundaries** - Graceful error handling
- **Audit Logging** - Activity tracking

## Performance

- **Code Splitting** - Lazy loading for optimal performance
- **Memoization** - React.memo and useMemo optimization
- **Virtual Scrolling** - Handle large datasets
- **Compression** - Gzip compression for production
- **Caching** - RTK Query caching strategies

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Contributing

1. Follow TypeScript best practices
2. Use Material-UI components consistently
3. Implement proper error handling
4. Write comprehensive tests
5. Update documentation

## License

MIT License - see LICENSE file for details.