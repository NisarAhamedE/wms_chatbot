import React, { useState, useCallback, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  IconButton,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Checkbox,
  FormControlLabel,
  LinearProgress,
  Alert,
  Tooltip,
  Badge,
  Menu,
  Fab,
  Collapse,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  Folder as FolderIcon,
  InsertDriveFile as FileIcon,
  Image as ImageIcon,
  VideoFile as VideoIcon,
  AudioFile as AudioIcon,
  PictureAsPdf as PdfIcon,
  Description as DocIcon,
  Delete as DeleteIcon,
  Download as DownloadIcon,
  Visibility as ViewIcon,
  Edit as EditIcon,
  FilterList as FilterIcon,
  Search as SearchIcon,
  GridView as GridViewIcon,
  ViewList as ListViewIcon,
  Sort as SortIcon,
  MoreVert as MoreVertIcon,
  Refresh as RefreshIcon,
  Add as AddIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Schedule as ProcessingIcon,
  Label as TagIcon,
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import { useSelector, useDispatch } from 'react-redux';
import { RootState } from '@/store/store';
import {
  useGetFilesQuery,
  useUploadFilesMutation,
  useDeleteFileMutation,
  useBulkActionMutation,
  useGetProcessingStatsQuery,
} from '@/services/filesApi';
import {
  setFiles,
  setFilters,
  setSorting,
  setPage,
  toggleFileSelection,
  selectAllFiles,
  clearSelection,
  updateFileManagementUI,
  setDragOver,
} from '@/store/slices/fileSlice';
import { addNotification } from '@/store/slices/uiSlice';
import LoadingSpinner from '@/components/common/LoadingSpinner';

interface FileUploadAreaProps {
  onFilesSelected: (files: FileList) => void;
  disabled?: boolean;
}

const FileUploadArea: React.FC<FileUploadAreaProps> = ({ onFilesSelected, disabled = false }) => {
  const dispatch = useDispatch();
  const { dragOver } = useSelector((state: RootState) => state.files);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const fileList = new DataTransfer();
      acceptedFiles.forEach(file => fileList.items.add(file));
      onFilesSelected(fileList.files);
    }
    dispatch(setDragOver(false));
  }, [onFilesSelected, dispatch]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    disabled,
    onDragEnter: () => dispatch(setDragOver(true)),
    onDragLeave: () => dispatch(setDragOver(false)),
    multiple: true,
    maxSize: 100 * 1024 * 1024, // 100MB
  });

  return (
    <Paper
      {...getRootProps()}
      sx={{
        p: 4,
        textAlign: 'center',
        border: '2px dashed',
        borderColor: isDragActive || dragOver ? 'primary.main' : 'grey.300',
        backgroundColor: isDragActive || dragOver ? 'action.hover' : 'background.default',
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'all 0.2s ease-in-out',
        '&:hover': {
          borderColor: disabled ? 'grey.300' : 'primary.main',
          backgroundColor: disabled ? 'background.default' : 'action.hover',
        },
      }}
    >
      <input {...getInputProps()} />
      <UploadIcon 
        sx={{ 
          fontSize: 48, 
          color: isDragActive || dragOver ? 'primary.main' : 'grey.400',
          mb: 2 
        }} 
      />
      <Typography variant="h6" gutterBottom>
        {isDragActive ? 'Drop files here' : 'Drag & drop files here'}
      </Typography>
      <Typography variant="body2" color="text.secondary" paragraph>
        or click to browse files
      </Typography>
      <Typography variant="caption" color="text.secondary">
        Supports: Documents, Images, Audio, Video (Max 100MB per file)
      </Typography>
    </Paper>
  );
};

const FileManagementPage: React.FC = () => {
  const dispatch = useDispatch();
  const { 
    files, 
    selectedFiles, 
    filters, 
    sortBy, 
    sortOrder, 
    currentPage, 
    itemsPerPage,
    totalCount,
    loading 
  } = useSelector((state: RootState) => state.files);
  
  const { viewMode, showFilters, showUploadArea } = useSelector(
    (state: RootState) => state.ui.fileManagement
  );

  const [uploadFiles] = useUploadFilesMutation();
  const [deleteFile] = useDeleteFileMutation();
  const [bulkAction] = useBulkActionMutation();

  const { 
    data: filesData, 
    isLoading: filesLoading, 
    refetch: refetchFiles 
  } = useGetFilesQuery({
    page: currentPage,
    limit: itemsPerPage,
    ...filters,
    sortBy,
    sortOrder,
  });

  const { data: processingStats } = useGetProcessingStatsQuery();

  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [uploading, setUploading] = useState(false);
  const [bulkDialogOpen, setBulkDialogOpen] = useState(false);
  const [filterMenuAnchor, setFilterMenuAnchor] = useState<null | HTMLElement>(null);

  // WMS Categories
  const wmsCategories = [
    'Wave Management',
    'Allocation',
    'Locating and Putaway',
    'Picking',
    'Cycle Counting',
    'Replenishment',
    'Labor Management',
    'Yard Management',
    'Slotting',
    'Cross-Docking',
    'Returns Management',
    'Inventory Management',
    'Order Management',
    'Task Management',
    'Reports and Analytics',
    'Other',
  ];

  // Update files in Redux when API data changes
  useEffect(() => {
    if (filesData) {
      dispatch(setFiles({
        files: filesData.files,
        totalCount: filesData.totalCount,
      }));
    }
  }, [filesData, dispatch]);

  // Handle file upload
  const handleFileUpload = async (fileList: FileList) => {
    if (!selectedCategory) {
      dispatch(addNotification({
        type: 'warning',
        title: 'Category Required',
        message: 'Please select a category before uploading files',
        autoHide: true,
        duration: 4000,
      }));
      return;
    }

    setUploading(true);

    try {
      const result = await uploadFiles({
        files: fileList,
        category: selectedCategory,
        source: 'upload',
        tags: [],
      }).unwrap();

      dispatch(addNotification({
        type: 'success',
        title: 'Upload Successful',
        message: `${result.files.length} files uploaded successfully`,
        autoHide: true,
        duration: 3000,
      }));

      refetchFiles();
    } catch (error: any) {
      dispatch(addNotification({
        type: 'error',
        title: 'Upload Failed',
        message: error?.data?.message || 'Failed to upload files',
        autoHide: true,
        duration: 5000,
      }));
    } finally {
      setUploading(false);
    }
  };

  // Handle search
  const handleSearch = () => {
    dispatch(setFilters({ searchTerm }));
    dispatch(setPage(1));
  };

  // Handle filter changes
  const handleFilterChange = (filterType: string, value: any) => {
    const newFilters = { ...filters };
    
    switch (filterType) {
      case 'category':
        newFilters.category = value ? [value] : [];
        break;
      case 'status':
        newFilters.status = value ? [value] : [];
        break;
      default:
        break;
    }
    
    dispatch(setFilters(newFilters));
    dispatch(setPage(1));
  };

  // Handle sort change
  const handleSortChange = (field: string) => {
    const newOrder = sortBy === field && sortOrder === 'desc' ? 'asc' : 'desc';
    dispatch(setSorting({ sortBy: field as any, sortOrder: newOrder }));
  };

  // Handle file selection
  const handleFileSelect = (fileId: string) => {
    dispatch(toggleFileSelection(fileId));
  };

  // Handle select all
  const handleSelectAll = () => {
    if (selectedFiles.length === files.length) {
      dispatch(clearSelection());
    } else {
      dispatch(selectAllFiles());
    }
  };

  // Handle bulk actions
  const handleBulkAction = async (action: string) => {
    if (selectedFiles.length === 0) return;

    try {
      await bulkAction({
        fileIds: selectedFiles,
        action,
      }).unwrap();

      dispatch(addNotification({
        type: 'success',
        title: 'Bulk Action Completed',
        message: `${action} completed for ${selectedFiles.length} files`,
        autoHide: true,
        duration: 3000,
      }));

      dispatch(clearSelection());
      refetchFiles();
      setBulkDialogOpen(false);
    } catch (error: any) {
      dispatch(addNotification({
        type: 'error',
        title: 'Bulk Action Failed',
        message: error?.data?.message || 'Failed to complete bulk action',
        autoHide: true,
        duration: 5000,
      }));
    }
  };

  // Get file icon
  const getFileIcon = (fileType: string, mimeType: string) => {
    if (mimeType.startsWith('image/')) return <ImageIcon />;
    if (mimeType.startsWith('video/')) return <VideoIcon />;
    if (mimeType.startsWith('audio/')) return <AudioIcon />;
    if (mimeType.includes('pdf')) return <PdfIcon />;
    if (mimeType.includes('document') || mimeType.includes('word')) return <DocIcon />;
    return <FileIcon />;
  };

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckIcon color="success" />;
      case 'processing':
        return <ProcessingIcon color="warning" />;
      case 'failed':
        return <ErrorIcon color="error" />;
      default:
        return <ProcessingIcon />;
    }
  };

  // Render file item
  const renderFileItem = (file: any) => (
    <Card 
      key={file.id} 
      sx={{ 
        mb: 1,
        backgroundColor: selectedFiles.includes(file.id) ? 'action.selected' : 'background.paper',
      }}
    >
      <CardContent sx={{ py: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Checkbox
            checked={selectedFiles.includes(file.id)}
            onChange={() => handleFileSelect(file.id)}
          />
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {getFileIcon(file.fileType, file.mimeType)}
            {getStatusIcon(file.status)}
          </Box>
          
          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            <Typography variant="subtitle2" noWrap>
              {file.originalName}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
              <Typography variant="caption" color="text.secondary">
                {(file.fileSize / 1024 / 1024).toFixed(2)} MB
              </Typography>
              <Typography variant="caption" color="text.secondary">
                •
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {new Date(file.uploadedAt).toLocaleDateString()}
              </Typography>
              {file.categories.length > 0 && (
                <>
                  <Typography variant="caption" color="text.secondary">
                    •
                  </Typography>
                  <Chip 
                    size="small" 
                    label={file.categories[0]} 
                    variant="outlined"
                  />
                </>
              )}
            </Box>
          </Box>
          
          {file.status === 'processing' && (
            <Box sx={{ width: 100 }}>
              <LinearProgress 
                variant="determinate" 
                value={file.processingProgress} 
                sx={{ height: 6, borderRadius: 3 }}
              />
              <Typography variant="caption" color="text.secondary" textAlign="center">
                {file.processingProgress}%
              </Typography>
            </Box>
          )}
          
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Tooltip title="View">
              <IconButton size="small">
                <ViewIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Download">
              <IconButton size="small">
                <DownloadIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="More actions">
              <IconButton size="small">
                <MoreVertIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            File Management
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Upload, process, and manage your WMS documents and media files
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => refetchFiles()}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => dispatch(updateFileManagementUI({ showUploadArea: !showUploadArea }))}
          >
            Upload Files
          </Button>
        </Box>
      </Box>

      {/* Processing Stats */}
      {processingStats && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Processing Overview
            </Typography>
            <Grid container spacing={3}>
              <Grid item xs={6} sm={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" color="primary">
                    {processingStats.totalFiles}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Total Files
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" color="warning.main">
                    {processingStats.processingFiles}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Processing
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" color="success.main">
                    {processingStats.completedFiles}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Completed
                  </Typography>
                </Box>
              </Grid>
              <Grid item xs={6} sm={3}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h4" color="error.main">
                    {processingStats.failedFiles}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Failed
                  </Typography>
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Upload Area */}
      <Collapse in={showUploadArea}>
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Upload Files
            </Typography>
            
            <FormControl fullWidth sx={{ mb: 3 }}>
              <InputLabel>Select WMS Category</InputLabel>
              <Select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                label="Select WMS Category"
              >
                {wmsCategories.map((category) => (
                  <MenuItem key={category} value={category}>
                    {category}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FileUploadArea
              onFilesSelected={handleFileUpload}
              disabled={uploading || !selectedCategory}
            />

            {uploading && (
              <Box sx={{ mt: 2 }}>
                <LinearProgress />
                <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ mt: 1 }}>
                  Uploading and processing files...
                </Typography>
              </Box>
            )}
          </CardContent>
        </Card>
      </Collapse>

      {/* Filters and Controls */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <TextField
              size="small"
              placeholder="Search files..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              InputProps={{
                startAdornment: <SearchIcon sx={{ mr: 1, color: 'action.active' }} />,
              }}
              sx={{ minWidth: 200 }}
            />
            
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Category</InputLabel>
              <Select
                value={categoryFilter}
                onChange={(e) => {
                  setCategoryFilter(e.target.value);
                  handleFilterChange('category', e.target.value);
                }}
                label="Category"
              >
                <MenuItem value="">All Categories</MenuItem>
                {wmsCategories.map((category) => (
                  <MenuItem key={category} value={category}>
                    {category}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  handleFilterChange('status', e.target.value);
                }}
                label="Status"
              >
                <MenuItem value="">All Status</MenuItem>
                <MenuItem value="completed">Completed</MenuItem>
                <MenuItem value="processing">Processing</MenuItem>
                <MenuItem value="failed">Failed</MenuItem>
              </Select>
            </FormControl>

            <Box sx={{ ml: 'auto', display: 'flex', gap: 1 }}>
              {selectedFiles.length > 0 && (
                <Button
                  variant="outlined"
                  onClick={() => setBulkDialogOpen(true)}
                  startIcon={<Badge badgeContent={selectedFiles.length} color="primary" />}
                >
                  Bulk Actions
                </Button>
              )}
              
              <IconButton
                onClick={() => dispatch(updateFileManagementUI({ 
                  viewMode: viewMode === 'list' ? 'grid' : 'list' 
                }))}
              >
                {viewMode === 'list' ? <GridViewIcon /> : <ListViewIcon />}
              </IconButton>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {/* File List */}
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">
              Files ({totalCount})
            </Typography>
            
            {files.length > 0 && (
              <FormControlLabel
                control={
                  <Checkbox
                    indeterminate={selectedFiles.length > 0 && selectedFiles.length < files.length}
                    checked={files.length > 0 && selectedFiles.length === files.length}
                    onChange={handleSelectAll}
                  />
                }
                label="Select All"
              />
            )}
          </Box>

          {filesLoading || loading ? (
            <LoadingSpinner message="Loading files..." />
          ) : files.length === 0 ? (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <FolderIcon sx={{ fontSize: 64, color: 'grey.400', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No files found
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Upload your first file to get started
              </Typography>
            </Box>
          ) : (
            <Box>
              {files.map(renderFileItem)}
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Bulk Actions Dialog */}
      <Dialog open={bulkDialogOpen} onClose={() => setBulkDialogOpen(false)}>
        <DialogTitle>
          Bulk Actions ({selectedFiles.length} files selected)
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" paragraph>
            Select an action to perform on all selected files:
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            <Button
              variant="outlined"
              onClick={() => handleBulkAction('reprocess')}
              startIcon={<RefreshIcon />}
            >
              Reprocess Files
            </Button>
            <Button
              variant="outlined"
              onClick={() => handleBulkAction('export')}
              startIcon={<DownloadIcon />}
            >
              Export Files
            </Button>
            <Button
              variant="outlined"
              color="error"
              onClick={() => handleBulkAction('delete')}
              startIcon={<DeleteIcon />}
            >
              Delete Files
            </Button>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBulkDialogOpen(false)}>Cancel</Button>
        </DialogActions>
      </Dialog>

      {/* Floating Action Button */}
      <Fab
        color="primary"
        aria-label="upload"
        sx={{ position: 'fixed', bottom: 16, right: 16 }}
        onClick={() => dispatch(updateFileManagementUI({ showUploadArea: true }))}
      >
        <UploadIcon />
      </Fab>
    </Box>
  );
};

export default FileManagementPage;