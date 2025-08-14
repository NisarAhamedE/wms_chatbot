import React, { useEffect, useState } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  IconButton,
  Menu,
  MenuItem,
  Chip,
  LinearProgress,
  Avatar,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Divider,
  Button,
  Paper,
} from '@mui/material';
import {
  MoreVert as MoreVertIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Folder as FolderIcon,
  Chat as ChatIcon,
  Storage as StorageIcon,
  Speed as SpeedIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Schedule as ScheduleIcon,
  Upload as UploadIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import { RootState } from '@/store/store';
import { 
  useGetProcessingStatsQuery,
  useGetFilesByCategoryQuery,
  useGetProcessingHistoryQuery 
} from '@/services/filesApi';
import { 
  useGetChatStatsQuery,
  useGetAgentPerformanceQuery 
} from '@/services/chatApi';
import { useGetDatabaseStatsQuery } from '@/services/databaseApi';
import { addNotification, updateDashboardUI } from '@/store/slices/uiSlice';
import LoadingSpinner from '@/components/common/LoadingSpinner';

interface StatCardProps {
  title: string;
  value: string | number;
  change?: number;
  changeType?: 'increase' | 'decrease';
  icon: React.ReactNode;
  color: 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info';
  loading?: boolean;
  onClick?: () => void;
}

const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  change,
  changeType,
  icon,
  color,
  loading = false,
  onClick,
}) => {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  return (
    <Card 
      sx={{ 
        height: '100%', 
        cursor: onClick ? 'pointer' : 'default',
        '&:hover': onClick ? { boxShadow: 4 } : {},
      }}
      onClick={onClick}
    >
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Avatar sx={{ bgcolor: `${color}.main`, width: 48, height: 48 }}>
              {icon}
            </Avatar>
            <Box>
              <Typography variant="h4" component="div" fontWeight="bold">
                {loading ? <LoadingSpinner size="small" /> : value}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {title}
              </Typography>
            </Box>
          </Box>
          <IconButton size="small" onClick={handleMenuOpen}>
            <MoreVertIcon />
          </IconButton>
        </Box>

        {change !== undefined && (
          <Box sx={{ display: 'flex', alignItems: 'center', mt: 2 }}>
            {changeType === 'increase' ? (
              <TrendingUpIcon color="success" fontSize="small" />
            ) : (
              <TrendingDownIcon color="error" fontSize="small" />
            )}
            <Typography
              variant="body2"
              color={changeType === 'increase' ? 'success.main' : 'error.main'}
              sx={{ ml: 0.5 }}
            >
              {Math.abs(change)}% from last period
            </Typography>
          </Box>
        )}

        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleMenuClose}
        >
          <MenuItem onClick={handleMenuClose}>View Details</MenuItem>
          <MenuItem onClick={handleMenuClose}>Export Data</MenuItem>
          <MenuItem onClick={handleMenuClose}>Configure</MenuItem>
        </Menu>
      </CardContent>
    </Card>
  );
};

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { timeRange, autoRefresh } = useSelector((state: RootState) => state.ui.dashboard);

  // API queries
  const { 
    data: processingStats, 
    isLoading: processingStatsLoading,
    refetch: refetchProcessingStats 
  } = useGetProcessingStatsQuery();

  const { 
    data: filesByCategory, 
    isLoading: filesByCategoryLoading 
  } = useGetFilesByCategoryQuery();

  const { 
    data: processingHistory, 
    isLoading: processingHistoryLoading 
  } = useGetProcessingHistoryQuery({ days: 7 });

  const { 
    data: chatStats, 
    isLoading: chatStatsLoading 
  } = useGetChatStatsQuery({ 
    dateRange: {
      start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      end: new Date().toISOString(),
    }
  });

  const { 
    data: agentPerformance, 
    isLoading: agentPerformanceLoading 
  } = useGetAgentPerformanceQuery({
    dateRange: {
      start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      end: new Date().toISOString(),
    }
  });

  const { 
    data: databaseStats, 
    isLoading: databaseStatsLoading 
  } = useGetDatabaseStatsQuery({
    dateRange: {
      start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      end: new Date().toISOString(),
    }
  });

  // Auto-refresh functionality
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        refetchProcessingStats();
      }, 30000); // Refresh every 30 seconds

      return () => clearInterval(interval);
    }
  }, [autoRefresh, refetchProcessingStats]);

  // Quick actions
  const handleQuickAction = (action: string) => {
    switch (action) {
      case 'upload':
        navigate('/files?action=upload');
        break;
      case 'chat':
        navigate('/chatbot');
        break;
      case 'query':
        navigate('/database/query');
        break;
      case 'refresh':
        refetchProcessingStats();
        dispatch(addNotification({
          type: 'info',
          title: 'Dashboard Refreshed',
          message: 'All data has been updated',
          autoHide: true,
          duration: 2000,
        }));
        break;
      default:
        break;
    }
  };

  // Recent activities (mock data - would come from API)
  const recentActivities = [
    {
      id: '1',
      type: 'file_upload',
      title: 'Document uploaded',
      description: 'warehouse_layout.pdf processed successfully',
      timestamp: '2 minutes ago',
      status: 'success',
    },
    {
      id: '2',
      type: 'chat_session',
      title: 'Chat session started',
      description: 'Wave Management agent activated',
      timestamp: '5 minutes ago',
      status: 'info',
    },
    {
      id: '3',
      type: 'database_query',
      title: 'Database query executed',
      description: 'Inventory levels query completed',
      timestamp: '10 minutes ago',
      status: 'success',
    },
    {
      id: '4',
      type: 'processing_error',
      title: 'Processing failed',
      description: 'audio_instruction.mp3 failed to process',
      timestamp: '15 minutes ago',
      status: 'error',
    },
  ];

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'file_upload':
        return <UploadIcon />;
      case 'chat_session':
        return <ChatIcon />;
      case 'database_query':
        return <StorageIcon />;
      case 'processing_error':
        return <ErrorIcon />;
      default:
        return <ScheduleIcon />;
    }
  };

  const getActivityColor = (status: string) => {
    switch (status) {
      case 'success':
        return 'success';
      case 'error':
        return 'error';
      case 'warning':
        return 'warning';
      default:
        return 'info';
    }
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            Dashboard
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Welcome back! Here's what's happening with your WMS system.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => handleQuickAction('refresh')}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<UploadIcon />}
            onClick={() => handleQuickAction('upload')}
          >
            Upload Files
          </Button>
        </Box>
      </Box>

      {/* Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Total Files"
            value={processingStats?.totalFiles || 0}
            change={12}
            changeType="increase"
            icon={<FolderIcon />}
            color="primary"
            loading={processingStatsLoading}
            onClick={() => navigate('/files')}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Processing"
            value={processingStats?.processingFiles || 0}
            icon={<SpeedIcon />}
            color="warning"
            loading={processingStatsLoading}
            onClick={() => navigate('/files?status=processing')}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Chat Sessions"
            value={chatStats?.totalSessions || 0}
            change={8}
            changeType="increase"
            icon={<ChatIcon />}
            color="info"
            loading={chatStatsLoading}
            onClick={() => navigate('/chatbot')}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            title="Database Queries"
            value={databaseStats?.totalQueries || 0}
            change={5}
            changeType="increase"
            icon={<StorageIcon />}
            color="success"
            loading={databaseStatsLoading}
            onClick={() => navigate('/database')}
          />
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        {/* Processing Overview */}
        <Grid item xs={12} lg={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Processing Overview
              </Typography>
              
              {processingStatsLoading ? (
                <LoadingSpinner />
              ) : (
                <Box>
                  <Box sx={{ mb: 3 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Typography variant="body2">Completed Files</Typography>
                      <Typography variant="body2">
                        {processingStats?.completedFiles}/{processingStats?.totalFiles}
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={
                        processingStats?.totalFiles
                          ? (processingStats.completedFiles / processingStats.totalFiles) * 100
                          : 0
                      }
                      sx={{ height: 8, borderRadius: 4 }}
                    />
                  </Box>

                  <Grid container spacing={2}>
                    <Grid item xs={6} sm={3}>
                      <Box sx={{ textAlign: 'center' }}>
                        <Typography variant="h6" color="success.main">
                          {processingStats?.completedFiles || 0}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Completed
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Box sx={{ textAlign: 'center' }}>
                        <Typography variant="h6" color="warning.main">
                          {processingStats?.processingFiles || 0}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Processing
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Box sx={{ textAlign: 'center' }}>
                        <Typography variant="h6" color="error.main">
                          {processingStats?.failedFiles || 0}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Failed
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={6} sm={3}>
                      <Box sx={{ textAlign: 'center' }}>
                        <Typography variant="h6" color="info.main">
                          {processingStats?.vectorizedFiles || 0}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Vectorized
                        </Typography>
                      </Box>
                    </Grid>
                  </Grid>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Quick Actions */}
        <Grid item xs={12} lg={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Quick Actions
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={<UploadIcon />}
                    onClick={() => handleQuickAction('upload')}
                    sx={{ py: 1.5 }}
                  >
                    Upload
                  </Button>
                </Grid>
                <Grid item xs={6}>
                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={<ChatIcon />}
                    onClick={() => handleQuickAction('chat')}
                    sx={{ py: 1.5 }}
                  >
                    Chat
                  </Button>
                </Grid>
                <Grid item xs={6}>
                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={<StorageIcon />}
                    onClick={() => handleQuickAction('query')}
                    sx={{ py: 1.5 }}
                  >
                    Query
                  </Button>
                </Grid>
                <Grid item xs={6}>
                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={<DownloadIcon />}
                    onClick={() => navigate('/files?action=export')}
                    sx={{ py: 1.5 }}
                  >
                    Export
                  </Button>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* File Categories */}
        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Files by Category
              </Typography>
              
              {filesByCategoryLoading ? (
                <LoadingSpinner />
              ) : (
                <Box>
                  {Object.entries(filesByCategory || {}).map(([category, count]) => (
                    <Box key={category} sx={{ mb: 2 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="body2">{category}</Typography>
                        <Chip size="small" label={count} />
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={processingStats?.totalFiles ? (count / processingStats.totalFiles) * 100 : 0}
                        sx={{ height: 6, borderRadius: 3 }}
                      />
                    </Box>
                  ))}
                  {(!filesByCategory || Object.keys(filesByCategory).length === 0) && (
                    <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ py: 2 }}>
                      No files uploaded yet
                    </Typography>
                  )}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Recent Activity */}
        <Grid item xs={12} lg={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Activity
              </Typography>
              
              <List disablePadding>
                {recentActivities.map((activity, index) => (
                  <React.Fragment key={activity.id}>
                    <ListItem disablePadding>
                      <ListItemAvatar>
                        <Avatar
                          sx={{
                            bgcolor: `${getActivityColor(activity.status)}.main`,
                            width: 32,
                            height: 32,
                          }}
                        >
                          {getActivityIcon(activity.type)}
                        </Avatar>
                      </ListItemAvatar>
                      <ListItemText
                        primary={activity.title}
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              {activity.description}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {activity.timestamp}
                            </Typography>
                          </Box>
                        }
                      />
                    </ListItem>
                    {index < recentActivities.length - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardPage;