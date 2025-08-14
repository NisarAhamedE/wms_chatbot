import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Container,
  Link,
  Alert,
  InputAdornment,
  IconButton,
  FormControlLabel,
  Checkbox,
  Divider,
  Grid,
  Card,
  CardContent,
} from '@mui/material';
import {
  Visibility,
  VisibilityOff,
  Person as PersonIcon,
  Lock as LockIcon,
  Login as LoginIcon,
  Warehouse as WarehouseIcon,
} from '@mui/icons-material';
import { useNavigate, Navigate } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { RootState } from '@/store/store';
import { useLoginMutation } from '@/services/authApi';
import { loginStart, loginSuccess, loginFailure, clearError } from '@/store/slices/authSlice';
import { addNotification } from '@/store/slices/uiSlice';
import LoadingSpinner from '@/components/common/LoadingSpinner';

interface LoginFormData {
  username: string;
  password: string;
  rememberMe: boolean;
}

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { isAuthenticated, loading, error, loginAttempts } = useSelector(
    (state: RootState) => state.auth
  );

  const [login, { isLoading: isLoginLoading }] = useLoginMutation();

  const [formData, setFormData] = useState<LoginFormData>({
    username: '',
    password: '',
    rememberMe: false,
  });

  const [showPassword, setShowPassword] = useState(false);
  const [formErrors, setFormErrors] = useState<Partial<LoginFormData>>({});

  // Redirect if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  // Clear errors when component mounts
  useEffect(() => {
    dispatch(clearError());
  }, [dispatch]);

  // Validate form
  const validateForm = (): boolean => {
    const errors: Partial<LoginFormData> = {};

    if (!formData.username.trim()) {
      errors.username = 'Username is required';
    }

    if (!formData.password) {
      errors.password = 'Password is required';
    } else if (formData.password.length < 6) {
      errors.password = 'Password must be at least 6 characters';
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  // Handle form submission
  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!validateForm()) {
      return;
    }

    try {
      dispatch(loginStart());

      const result = await login({
        username: formData.username,
        password: formData.password,
        rememberMe: formData.rememberMe,
      }).unwrap();

      dispatch(loginSuccess(result));
      
      dispatch(addNotification({
        type: 'success',
        title: 'Login Successful',
        message: `Welcome back, ${result.user.username}!`,
        autoHide: true,
        duration: 3000,
      }));

      navigate('/dashboard');
    } catch (error: any) {
      const errorMessage = error?.data?.message || error?.message || 'Login failed. Please try again.';
      
      dispatch(loginFailure(errorMessage));
      
      dispatch(addNotification({
        type: 'error',
        title: 'Login Failed',
        message: errorMessage,
        autoHide: true,
        duration: 5000,
      }));
    }
  };

  // Handle input changes
  const handleInputChange = (field: keyof LoginFormData) => (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const value = field === 'rememberMe' ? event.target.checked : event.target.value;
    
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));

    // Clear field error when user starts typing
    if (formErrors[field]) {
      setFormErrors(prev => ({
        ...prev,
        [field]: undefined,
      }));
    }

    // Clear global error
    if (error) {
      dispatch(clearError());
    }
  };

  // Toggle password visibility
  const handleTogglePassword = () => {
    setShowPassword(!showPassword);
  };

  // Handle forgot password
  const handleForgotPassword = () => {
    navigate('/forgot-password');
  };

  const isFormLoading = loading || isLoginLoading;

  return (
    <Container component="main" maxWidth="lg">
      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          py: 3,
        }}
      >
        <Grid container spacing={4} alignItems="center">
          {/* Left Side - Branding */}
          <Grid item xs={12} md={6}>
            <Box sx={{ textAlign: { xs: 'center', md: 'left' }, mb: { xs: 4, md: 0 } }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: { xs: 'center', md: 'flex-start' }, mb: 3 }}>
                <WarehouseIcon sx={{ fontSize: 48, color: 'primary.main', mr: 2 }} />
                <Typography variant="h3" component="h1" fontWeight="bold">
                  WMS Chatbot
                </Typography>
              </Box>
              
              <Typography variant="h5" color="text.secondary" paragraph>
                Warehouse Management System
              </Typography>
              
              <Typography variant="body1" color="text.secondary" paragraph>
                Streamline your warehouse operations with our intelligent chatbot system. 
                Get instant access to 16 specialized WMS categories with 80 expert agents.
              </Typography>

              <Grid container spacing={2} sx={{ mt: 3 }}>
                <Grid item xs={12} sm={6}>
                  <Card variant="outlined">
                    <CardContent sx={{ textAlign: 'center', py: 2 }}>
                      <Typography variant="h6" color="primary">
                        16
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        WMS Categories
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Card variant="outlined">
                    <CardContent sx={{ textAlign: 'center', py: 2 }}>
                      <Typography variant="h6" color="primary">
                        80
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Specialized Agents
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            </Box>
          </Grid>

          {/* Right Side - Login Form */}
          <Grid item xs={12} md={6}>
            <Paper
              elevation={8}
              sx={{
                p: 4,
                maxWidth: 400,
                mx: 'auto',
                borderRadius: 2,
              }}
            >
              <Box sx={{ textAlign: 'center', mb: 3 }}>
                <Typography variant="h4" component="h2" gutterBottom>
                  Sign In
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Access your WMS dashboard
                </Typography>
              </Box>

              {error && (
                <Alert severity="error" sx={{ mb: 3 }}>
                  {error}
                  {loginAttempts >= 3 && (
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      Multiple failed attempts detected. Please check your credentials.
                    </Typography>
                  )}
                </Alert>
              )}

              <Box component="form" onSubmit={handleSubmit} noValidate>
                <TextField
                  fullWidth
                  id="username"
                  label="Username"
                  value={formData.username}
                  onChange={handleInputChange('username')}
                  error={!!formErrors.username}
                  helperText={formErrors.username}
                  margin="normal"
                  autoComplete="username"
                  autoFocus
                  disabled={isFormLoading}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <PersonIcon color="action" />
                      </InputAdornment>
                    ),
                  }}
                />

                <TextField
                  fullWidth
                  id="password"
                  label="Password"
                  type={showPassword ? 'text' : 'password'}
                  value={formData.password}
                  onChange={handleInputChange('password')}
                  error={!!formErrors.password}
                  helperText={formErrors.password}
                  margin="normal"
                  autoComplete="current-password"
                  disabled={isFormLoading}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <LockIcon color="action" />
                      </InputAdornment>
                    ),
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          aria-label="toggle password visibility"
                          onClick={handleTogglePassword}
                          edge="end"
                          disabled={isFormLoading}
                        >
                          {showPassword ? <VisibilityOff /> : <Visibility />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />

                <FormControlLabel
                  control={
                    <Checkbox
                      checked={formData.rememberMe}
                      onChange={handleInputChange('rememberMe')}
                      disabled={isFormLoading}
                      color="primary"
                    />
                  }
                  label="Remember me"
                  sx={{ mt: 1 }}
                />

                <Button
                  type="submit"
                  fullWidth
                  variant="contained"
                  size="large"
                  disabled={isFormLoading}
                  startIcon={isFormLoading ? <LoadingSpinner size="small" /> : <LoginIcon />}
                  sx={{ mt: 3, mb: 2, py: 1.5 }}
                >
                  {isFormLoading ? 'Signing In...' : 'Sign In'}
                </Button>

                <Box sx={{ textAlign: 'center' }}>
                  <Link
                    component="button"
                    variant="body2"
                    onClick={handleForgotPassword}
                    disabled={isFormLoading}
                  >
                    Forgot your password?
                  </Link>
                </Box>

                <Divider sx={{ my: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    Demo Access
                  </Typography>
                </Divider>

                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Demo credentials:
                  </Typography>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                    Username: <strong>demo</strong> | Password: <strong>demo123</strong>
                  </Typography>
                </Box>
              </Box>
            </Paper>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
};

export default LoginPage;