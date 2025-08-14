import React from 'react';
import {
  Box,
  CircularProgress,
  Typography,
  Paper,
  LinearProgress,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';

interface LoadingSpinnerProps {
  size?: number | 'small' | 'medium' | 'large';
  message?: string;
  variant?: 'circular' | 'linear' | 'overlay' | 'fullscreen';
  color?: 'primary' | 'secondary' | 'inherit';
  progress?: number;
  showProgress?: boolean;
  overlay?: boolean;
  backdrop?: boolean;
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'medium',
  message,
  variant = 'circular',
  color = 'primary',
  progress,
  showProgress = false,
  overlay = false,
  backdrop = false,
}) => {
  const theme = useTheme();

  const getSizeValue = () => {
    if (typeof size === 'number') return size;
    switch (size) {
      case 'small':
        return 24;
      case 'large':
        return 56;
      default:
        return 40;
    }
  };

  const renderCircularProgress = () => (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2,
      }}
    >
      <CircularProgress
        size={getSizeValue()}
        color={color}
        variant={showProgress && progress !== undefined ? 'determinate' : 'indeterminate'}
        value={progress}
      />
      {showProgress && progress !== undefined && (
        <Typography variant="body2" color="text.secondary">
          {Math.round(progress)}%
        </Typography>
      )}
      {message && (
        <Typography
          variant="body2"
          color="text.secondary"
          textAlign="center"
          sx={{ maxWidth: 300 }}
        >
          {message}
        </Typography>
      )}
    </Box>
  );

  const renderLinearProgress = () => (
    <Box sx={{ width: '100%', maxWidth: 400 }}>
      <LinearProgress
        color={color}
        variant={showProgress && progress !== undefined ? 'determinate' : 'indeterminate'}
        value={progress}
        sx={{ mb: message ? 1 : 0 }}
      />
      {message && (
        <Typography variant="body2" color="text.secondary" textAlign="center">
          {message}
        </Typography>
      )}
      {showProgress && progress !== undefined && (
        <Typography variant="body2" color="text.secondary" textAlign="center">
          {Math.round(progress)}%
        </Typography>
      )}
    </Box>
  );

  const renderContent = () => {
    switch (variant) {
      case 'linear':
        return renderLinearProgress();
      case 'circular':
      default:
        return renderCircularProgress();
    }
  };

  if (variant === 'fullscreen') {
    return (
      <Box
        sx={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: backdrop ? 'rgba(0, 0, 0, 0.5)' : 'transparent',
          zIndex: theme.zIndex.modal + 1,
        }}
      >
        {backdrop ? (
          <Paper
            elevation={8}
            sx={{
              p: 4,
              borderRadius: 2,
              backgroundColor: theme.palette.background.paper,
            }}
          >
            {renderContent()}
          </Paper>
        ) : (
          renderContent()
        )}
      </Box>
    );
  }

  if (variant === 'overlay' || overlay) {
    return (
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: backdrop ? 'rgba(255, 255, 255, 0.8)' : 'transparent',
          zIndex: theme.zIndex.modal,
        }}
      >
        {backdrop ? (
          <Paper
            elevation={4}
            sx={{
              p: 3,
              borderRadius: 2,
              backgroundColor: theme.palette.background.paper,
            }}
          >
            {renderContent()}
          </Paper>
        ) : (
          renderContent()
        )}
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        p: 2,
      }}
    >
      {renderContent()}
    </Box>
  );
};

export default LoadingSpinner;