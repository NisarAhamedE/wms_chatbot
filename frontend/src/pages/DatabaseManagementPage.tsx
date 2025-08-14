import React, { useState, useEffect } from 'react';
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
  ListItemButton,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Tab,
  Collapse,
  Alert,
  Tooltip,
  CircularProgress,
  Badge,
} from '@mui/material';
import {
  Storage as StorageIcon,
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
  PlayArrow as ExecuteIcon,
  Save as SaveIcon,
  History as HistoryIcon,
  Schema as SchemaIcon,
  TableChart as TableIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  CheckCircle as ConnectedIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Code as CodeIcon,
  Download as DownloadIcon,
  Visibility as ViewIcon,
} from '@mui/icons-material';
import { useSelector, useDispatch } from 'react-redux';
import { RootState } from '@/store/store';
import {
  useGetConnectionsQuery,
  useCreateConnectionMutation,
  useTestConnectionMutation,
  useDeleteConnectionMutation,
  useGetSchemaQuery,
  useExecuteQueryMutation,
  useGetQueryHistoryQuery,
  useGetSavedQueriesQuery,
  useSaveQueryMutation,
} from '@/services/databaseApi';
import { addNotification, updateDatabaseUI } from '@/store/slices/uiSlice';
import LoadingSpinner from '@/components/common/LoadingSpinner';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div hidden={value !== index}>
      {value === index && <Box>{children}</Box>}
    </div>
  );
};

const DatabaseManagementPage: React.FC = () => {
  const dispatch = useDispatch();
  const { showSchema, selectedTable, queryMode, showQueryHistory } = useSelector(
    (state: RootState) => state.ui.database
  );

  const [activeTab, setActiveTab] = useState(0);
  const [connectionDialogOpen, setConnectionDialogOpen] = useState(false);
  const [queryDialogOpen, setQueryDialogOpen] = useState(false);
  const [selectedConnection, setSelectedConnection] = useState<string>('');
  const [sqlQuery, setSqlQuery] = useState('');
  const [queryResults, setQueryResults] = useState<any>(null);
  const [executingQuery, setExecutingQuery] = useState(false);
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());

  // Connection form state
  const [connectionForm, setConnectionForm] = useState({
    name: '',
    type: 'postgresql' as 'postgresql' | 'mssql' | 'mysql',
    host: '',
    port: 5432,
    database: '',
    username: '',
    password: '',
    ssl: false,
  });

  // API hooks
  const { data: connections, refetch: refetchConnections } = useGetConnectionsQuery();
  const { data: schema } = useGetSchemaQuery(selectedConnection, {
    skip: !selectedConnection,
  });
  const { data: queryHistory } = useGetQueryHistoryQuery({
    connectionId: selectedConnection,
    limit: 50,
  });
  const { data: savedQueries } = useGetSavedQueriesQuery({});

  const [createConnection] = useCreateConnectionMutation();
  const [testConnection] = useTestConnectionMutation();
  const [deleteConnection] = useDeleteConnectionMutation();
  const [executeQuery] = useExecuteQueryMutation();
  const [saveQuery] = useSaveQueryMutation();

  // Handle connection creation
  const handleCreateConnection = async () => {
    try {
      await createConnection(connectionForm).unwrap();
      
      dispatch(addNotification({
        type: 'success',
        title: 'Connection Created',
        message: `Database connection "${connectionForm.name}" created successfully`,
        autoHide: true,
        duration: 3000,
      }));

      setConnectionDialogOpen(false);
      setConnectionForm({
        name: '',
        type: 'postgresql',
        host: '',
        port: 5432,
        database: '',
        username: '',
        password: '',
        ssl: false,
      });
      refetchConnections();
    } catch (error: any) {
      dispatch(addNotification({
        type: 'error',
        title: 'Connection Failed',
        message: error?.data?.message || 'Failed to create connection',
        autoHide: true,
        duration: 5000,
      }));
    }
  };

  // Handle connection test
  const handleTestConnection = async (connectionId: string) => {
    try {
      const result = await testConnection(connectionId).unwrap();
      
      dispatch(addNotification({
        type: result.success ? 'success' : 'error',
        title: 'Connection Test',
        message: result.message,
        autoHide: true,
        duration: 3000,
      }));
    } catch (error: any) {
      dispatch(addNotification({
        type: 'error',
        title: 'Connection Test Failed',
        message: error?.data?.message || 'Failed to test connection',
        autoHide: true,
        duration: 5000,
      }));
    }
  };

  // Handle query execution
  const handleExecuteQuery = async () => {
    if (!sqlQuery.trim() || !selectedConnection) return;

    setExecutingQuery(true);
    try {
      const result = await executeQuery({
        connectionId: selectedConnection,
        query: sqlQuery,
        limit: 1000,
      }).unwrap();

      setQueryResults(result);
      
      if (result.success) {
        dispatch(addNotification({
          type: 'success',
          title: 'Query Executed',
          message: `Query completed in ${result.executionTime}ms`,
          autoHide: true,
          duration: 3000,
        }));
      }
    } catch (error: any) {
      dispatch(addNotification({
        type: 'error',
        title: 'Query Failed',
        message: error?.data?.message || 'Failed to execute query',
        autoHide: true,
        duration: 5000,
      }));
    } finally {
      setExecutingQuery(false);
    }
  };

  // Handle save query
  const handleSaveQuery = async () => {
    if (!sqlQuery.trim()) return;

    try {
      await saveQuery({
        name: `Query ${Date.now()}`,
        query: sqlQuery,
        connectionId: selectedConnection,
        category: 'WMS',
        tags: [],
        isPublic: false,
        description: 'Query from database management',
      }).unwrap();

      dispatch(addNotification({
        type: 'success',
        title: 'Query Saved',
        message: 'Query saved successfully',
        autoHide: true,
        duration: 3000,
      }));
    } catch (error: any) {
      dispatch(addNotification({
        type: 'error',
        title: 'Save Failed',
        message: error?.data?.message || 'Failed to save query',
        autoHide: true,
        duration: 5000,
      }));
    }
  };

  // Toggle table expansion
  const toggleTableExpansion = (tableName: string) => {
    const newExpanded = new Set(expandedTables);
    if (newExpanded.has(tableName)) {
      newExpanded.delete(tableName);
    } else {
      newExpanded.add(tableName);
    }
    setExpandedTables(newExpanded);
  };

  // Get connection status icon
  const getConnectionStatusIcon = (status: string) => {
    switch (status) {
      case 'connected':
        return <ConnectedIcon color="success" />;
      case 'error':
        return <ErrorIcon color="error" />;
      default:
        return <WarningIcon color="warning" />;
    }
  };

  // Generate sample WMS queries
  const sampleQueries = [
    {
      name: 'Active Orders',
      query: 'SELECT order_id, order_status, created_date FROM orders WHERE order_status = \'ACTIVE\' LIMIT 100;',
      description: 'Get all active orders',
    },
    {
      name: 'Inventory Levels',
      query: 'SELECT item_id, location_id, quantity, reserved_qty FROM inventory WHERE quantity > 0 ORDER BY quantity DESC LIMIT 100;',
      description: 'Check current inventory levels',
    },
    {
      name: 'Wave Status',
      query: 'SELECT wave_id, wave_status, created_date, total_picks FROM waves WHERE wave_status IN (\'RELEASED\', \'PICKING\') LIMIT 50;',
      description: 'Monitor active waves',
    },
    {
      name: 'Pick Productivity',
      query: 'SELECT user_id, COUNT(*) as picks_completed, AVG(pick_time) as avg_time FROM pick_tasks WHERE completed_date >= CURRENT_DATE GROUP BY user_id LIMIT 50;',
      description: 'Daily pick productivity by user',
    },
  ];

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            Database Management
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Manage database connections and execute queries for your WMS system
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={() => refetchConnections()}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setConnectionDialogOpen(true)}
          >
            New Connection
          </Button>
        </Box>
      </Box>

      {/* Main Content */}
      <Grid container spacing={3}>
        {/* Left Panel - Connections & Schema */}
        <Grid item xs={12} md={4}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {/* Connections */}
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Database Connections
                </Typography>
                
                {connections && connections.length > 0 ? (
                  <List dense>
                    {connections.map((connection) => (
                      <ListItemButton
                        key={connection.id}
                        selected={selectedConnection === connection.id}
                        onClick={() => setSelectedConnection(connection.id)}
                      >
                        <ListItemIcon>
                          {getConnectionStatusIcon(connection.status)}
                        </ListItemIcon>
                        <ListItemText
                          primary={connection.name}
                          secondary={`${connection.type} • ${connection.host}:${connection.port}`}
                        />
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleTestConnection(connection.id);
                            }}
                          >
                            <RefreshIcon fontSize="small" />
                          </IconButton>
                          <IconButton size="small">
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Box>
                      </ListItemButton>
                    ))}
                  </List>
                ) : (
                  <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ py: 2 }}>
                    No connections configured
                  </Typography>
                )}
              </CardContent>
            </Card>

            {/* Schema Explorer */}
            {selectedConnection && showSchema && (
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Schema Explorer
                  </Typography>
                  
                  {schema ? (
                    <List dense>
                      {schema.tables.map((table) => {
                        const isExpanded = expandedTables.has(table.name);
                        return (
                          <React.Fragment key={table.name}>
                            <ListItemButton onClick={() => toggleTableExpansion(table.name)}>
                              <ListItemIcon>
                                <TableIcon />
                              </ListItemIcon>
                              <ListItemText
                                primary={table.name}
                                secondary={`${table.columns.length} columns`}
                              />
                              {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                            </ListItemButton>
                            
                            <Collapse in={isExpanded}>
                              <List component="div" disablePadding>
                                {table.columns.slice(0, 5).map((column) => (
                                  <ListItem key={column.name} sx={{ pl: 4 }}>
                                    <ListItemText
                                      primary={column.name}
                                      secondary={column.type}
                                    />
                                    {column.primaryKey && (
                                      <Chip size="small" label="PK" color="primary" />
                                    )}
                                  </ListItem>
                                ))}
                                {table.columns.length > 5 && (
                                  <ListItem sx={{ pl: 4 }}>
                                    <ListItemText
                                      secondary={`... and ${table.columns.length - 5} more columns`}
                                    />
                                  </ListItem>
                                )}
                              </List>
                            </Collapse>
                          </React.Fragment>
                        );
                      })}
                    </List>
                  ) : (
                    <LoadingSpinner message="Loading schema..." />
                  )}
                </CardContent>
              </Card>
            )}
          </Box>
        </Grid>

        {/* Right Panel - Query Interface */}
        <Grid item xs={12} md={8}>
          <Card sx={{ height: 'calc(100vh - 200px)' }}>
            <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
              <Tabs value={activeTab} onChange={(e, value) => setActiveTab(value)}>
                <Tab label="Query Builder" />
                <Tab label="Query History" />
                <Tab label="Saved Queries" />
                <Tab label="Sample Queries" />
              </Tabs>
            </Box>

            {/* Query Builder Tab */}
            <TabPanel value={activeTab} index={0}>
              <Box sx={{ p: 2, height: 'calc(100% - 48px)', display: 'flex', flexDirection: 'column' }}>
                {!selectedConnection ? (
                  <Box sx={{ textAlign: 'center', py: 4 }}>
                    <StorageIcon sx={{ fontSize: 64, color: 'grey.400', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary" gutterBottom>
                      Select a Database Connection
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Choose a connection from the left panel to start querying
                    </Typography>
                  </Box>
                ) : (
                  <>
                    {/* Query Input */}
                    <Box sx={{ mb: 2 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                        <Typography variant="subtitle1">SQL Query</Typography>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                          <Button
                            size="small"
                            onClick={handleSaveQuery}
                            disabled={!sqlQuery.trim()}
                            startIcon={<SaveIcon />}
                          >
                            Save
                          </Button>
                          <Button
                            variant="contained"
                            onClick={handleExecuteQuery}
                            disabled={!sqlQuery.trim() || executingQuery}
                            startIcon={executingQuery ? <CircularProgress size={16} /> : <ExecuteIcon />}
                          >
                            {executingQuery ? 'Executing...' : 'Execute'}
                          </Button>
                        </Box>
                      </Box>
                      <TextField
                        fullWidth
                        multiline
                        rows={8}
                        value={sqlQuery}
                        onChange={(e) => setSqlQuery(e.target.value)}
                        placeholder="Enter your SQL query here..."
                        variant="outlined"
                        sx={{
                          '& .MuiInputBase-input': {
                            fontFamily: 'monospace',
                            fontSize: '0.875rem',
                          },
                        }}
                      />
                    </Box>

                    {/* Query Results */}
                    <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
                      {queryResults ? (
                        queryResults.success ? (
                          <TableContainer component={Paper} variant="outlined">
                            <Table size="small">
                              <TableHead>
                                <TableRow>
                                  {queryResults.columns?.map((column: any) => (
                                    <TableCell key={column.name}>
                                      {column.name}
                                    </TableCell>
                                  ))}
                                </TableRow>
                              </TableHead>
                              <TableBody>
                                {queryResults.data?.map((row: any, index: number) => (
                                  <TableRow key={index}>
                                    {queryResults.columns?.map((column: any) => (
                                      <TableCell key={column.name}>
                                        {String(row[column.name] || '')}
                                      </TableCell>
                                    ))}
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </TableContainer>
                        ) : (
                          <Alert severity="error">
                            {queryResults.error}
                          </Alert>
                        )
                      ) : (
                        <Box sx={{ textAlign: 'center', py: 4 }}>
                          <CodeIcon sx={{ fontSize: 64, color: 'grey.400', mb: 2 }} />
                          <Typography variant="body1" color="text.secondary">
                            Execute a query to see results
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  </>
                )}
              </Box>
            </TabPanel>

            {/* Query History Tab */}
            <TabPanel value={activeTab} index={1}>
              <Box sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>
                  Query History
                </Typography>
                
                {queryHistory?.history && queryHistory.history.length > 0 ? (
                  <List>
                    {queryHistory.history.map((item) => (
                      <ListItem key={item.id}>
                        <ListItemText
                          primary={
                            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                              {item.query.length > 100 ? `${item.query.substring(0, 100)}...` : item.query}
                            </Typography>
                          }
                          secondary={
                            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mt: 0.5 }}>
                              <Chip size="small" label={item.success ? 'Success' : 'Failed'} 
                                color={item.success ? 'success' : 'error'} />
                              <Typography variant="caption" color="text.secondary">
                                {new Date(item.executedAt).toLocaleString()}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {item.executionTime}ms
                              </Typography>
                            </Box>
                          }
                        />
                        <IconButton
                          size="small"
                          onClick={() => setSqlQuery(item.query)}
                        >
                          <CodeIcon />
                        </IconButton>
                      </ListItem>
                    ))}
                  </List>
                ) : (
                  <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ py: 2 }}>
                    No query history available
                  </Typography>
                )}
              </Box>
            </TabPanel>

            {/* Saved Queries Tab */}
            <TabPanel value={activeTab} index={2}>
              <Box sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>
                  Saved Queries
                </Typography>
                
                {savedQueries?.queries && savedQueries.queries.length > 0 ? (
                  <List>
                    {savedQueries.queries.map((query) => (
                      <ListItem key={query.id}>
                        <ListItemText
                          primary={query.name}
                          secondary={query.description}
                        />
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                          <IconButton
                            size="small"
                            onClick={() => setSqlQuery(query.query)}
                          >
                            <ViewIcon />
                          </IconButton>
                          <IconButton size="small">
                            <EditIcon />
                          </IconButton>
                        </Box>
                      </ListItem>
                    ))}
                  </List>
                ) : (
                  <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ py: 2 }}>
                    No saved queries available
                  </Typography>
                )}
              </Box>
            </TabPanel>

            {/* Sample Queries Tab */}
            <TabPanel value={activeTab} index={3}>
              <Box sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>
                  Sample WMS Queries
                </Typography>
                
                <List>
                  {sampleQueries.map((query, index) => (
                    <ListItem key={index}>
                      <ListItemText
                        primary={query.name}
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              {query.description}
                            </Typography>
                            <Typography variant="caption" sx={{ fontFamily: 'monospace', mt: 0.5, display: 'block' }}>
                              {query.query}
                            </Typography>
                          </Box>
                        }
                      />
                      <IconButton
                        size="small"
                        onClick={() => setSqlQuery(query.query)}
                      >
                        <CodeIcon />
                      </IconButton>
                    </ListItem>
                  ))}
                </List>
              </Box>
            </TabPanel>
          </Card>
        </Grid>
      </Grid>

      {/* Connection Dialog */}
      <Dialog open={connectionDialogOpen} onClose={() => setConnectionDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Create Database Connection</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Connection Name"
                value={connectionForm.name}
                onChange={(e) => setConnectionForm({ ...connectionForm, name: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Database Type</InputLabel>
                <Select
                  value={connectionForm.type}
                  onChange={(e) => setConnectionForm({ 
                    ...connectionForm, 
                    type: e.target.value as any,
                    port: e.target.value === 'postgresql' ? 5432 : e.target.value === 'mysql' ? 3306 : 1433
                  })}
                  label="Database Type"
                >
                  <MenuItem value="postgresql">PostgreSQL</MenuItem>
                  <MenuItem value="mssql">SQL Server</MenuItem>
                  <MenuItem value="mysql">MySQL</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Host"
                value={connectionForm.host}
                onChange={(e) => setConnectionForm({ ...connectionForm, host: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Port"
                type="number"
                value={connectionForm.port}
                onChange={(e) => setConnectionForm({ ...connectionForm, port: parseInt(e.target.value) })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Database Name"
                value={connectionForm.database}
                onChange={(e) => setConnectionForm({ ...connectionForm, database: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Username"
                value={connectionForm.username}
                onChange={(e) => setConnectionForm({ ...connectionForm, username: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Password"
                type="password"
                value={connectionForm.password}
                onChange={(e) => setConnectionForm({ ...connectionForm, password: e.target.value })}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConnectionDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateConnection} variant="contained">
            Create Connection
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default DatabaseManagementPage;