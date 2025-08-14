import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  IconButton,
  Avatar,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemButton,
  Divider,
  Chip,
  Paper,
  Drawer,
  AppBar,
  Toolbar,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  Collapse,
  Badge,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import {
  Send as SendIcon,
  AttachFile as AttachIcon,
  SmartToy as BotIcon,
  Person as PersonIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Settings as SettingsIcon,
  History as HistoryIcon,
  Add as AddIcon,
  Close as CloseIcon,
  Menu as MenuIcon,
  Refresh as RefreshIcon,
  ContentCopy as CopyIcon,
  ThumbUp as ThumbUpIcon,
  ThumbDown as ThumbDownIcon,
  MoreVert as MoreVertIcon,
  Folder as FolderIcon,
  Download as DownloadIcon,
} from '@mui/icons-material';
import { useSelector, useDispatch } from 'react-redux';
import { RootState } from '@/store/store';
import {
  useCreateSessionMutation,
  useSendMessageMutation,
  useGetSessionsQuery,
  useGetMessagesQuery,
  useGetAgentsQuery,
} from '@/services/chatApi';
import {
  createSession,
  switchSession,
  addMessage,
  setInputValue,
  selectAgent,
  addContextFile,
  removeContextFile,
  updateChatbotUI,
} from '@/store/slices/chatSlice';
import { addNotification } from '@/store/slices/uiSlice';
import LoadingSpinner from '@/components/common/LoadingSpinner';

interface MessageProps {
  message: any;
  onReaction: (messageId: string, reaction: string) => void;
}

const MessageComponent: React.FC<MessageProps> = ({ message, onReaction }) => {
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setMenuAnchor(null);
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: message.role === 'user' ? 'row-reverse' : 'row',
        mb: 2,
        alignItems: 'flex-start',
        gap: 1,
      }}
    >
      <Avatar
        sx={{
          bgcolor: message.role === 'user' ? 'primary.main' : 'secondary.main',
          width: 32,
          height: 32,
        }}
      >
        {message.role === 'user' ? <PersonIcon /> : <BotIcon />}
      </Avatar>

      <Paper
        sx={{
          p: 2,
          maxWidth: '70%',
          backgroundColor: message.role === 'user' ? 'primary.light' : 'grey.100',
          color: message.role === 'user' ? 'primary.contrastText' : 'text.primary',
        }}
      >
        <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
          {message.content}
        </Typography>

        {message.metadata && (
          <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {message.agent && (
              <Chip size="small" label={message.agent} variant="outlined" />
            )}
            {message.category && (
              <Chip size="small" label={message.category} variant="outlined" />
            )}
            {message.metadata.confidence && (
              <Chip 
                size="small" 
                label={`${Math.round(message.metadata.confidence * 100)}% confidence`} 
                variant="outlined" 
              />
            )}
          </Box>
        )}

        {message.sources && message.sources.length > 0 && (
          <Box sx={{ mt: 1 }}>
            <Typography variant="caption" color="text.secondary" gutterBottom>
              Sources:
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
              {message.sources.map((source: string, index: number) => (
                <Chip
                  key={index}
                  size="small"
                  label={source}
                  variant="outlined"
                  icon={<FolderIcon />}
                  onClick={() => {/* Handle source click */}}
                />
              ))}
            </Box>
          </Box>
        )}

        <Box sx={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          mt: 1 
        }}>
          <Typography variant="caption" color="text.secondary">
            {formatTimestamp(message.timestamp)}
          </Typography>

          <Box sx={{ display: 'flex', gap: 0.5 }}>
            {message.role === 'assistant' && (
              <>
                <IconButton
                  size="small"
                  onClick={() => onReaction(message.id, 'helpful')}
                  color={message.reactions?.helpful ? 'primary' : 'default'}
                >
                  <ThumbUpIcon fontSize="small" />
                </IconButton>
                <IconButton
                  size="small"
                  onClick={() => onReaction(message.id, 'unhelpful')}
                  color={message.reactions?.helpful === false ? 'error' : 'default'}
                >
                  <ThumbDownIcon fontSize="small" />
                </IconButton>
              </>
            )}
            <IconButton size="small" onClick={handleCopy}>
              <CopyIcon fontSize="small" />
            </IconButton>
            <IconButton 
              size="small" 
              onClick={(e) => setMenuAnchor(e.currentTarget)}
            >
              <MoreVertIcon fontSize="small" />
            </IconButton>
          </Box>
        </Box>

        <Menu
          anchorEl={menuAnchor}
          open={Boolean(menuAnchor)}
          onClose={() => setMenuAnchor(null)}
        >
          <MenuItem onClick={handleCopy}>Copy Message</MenuItem>
          <MenuItem onClick={() => setMenuAnchor(null)}>Regenerate</MenuItem>
          <MenuItem onClick={() => setMenuAnchor(null)}>Report Issue</MenuItem>
        </Menu>
      </Paper>
    </Box>
  );
};

const ChatbotPage: React.FC = () => {
  const dispatch = useDispatch();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const {
    currentSession,
    messages,
    sessions,
    selectedAgent,
    availableAgents,
    contextFiles,
    inputValue,
    isProcessing,
  } = useSelector((state: RootState) => state.chat);

  const { showAgentPanel, showContextFiles, showHistory } = useSelector(
    (state: RootState) => state.ui.chatbot
  );

  const [createSessionMutation] = useCreateSessionMutation();
  const [sendMessage] = useSendMessageMutation();
  
  const { data: sessionsData } = useGetSessionsQuery({});
  const { data: messagesData } = useGetMessagesQuery(
    { sessionId: currentSession?.id || '' },
    { skip: !currentSession?.id }
  );
  const { data: agentsData } = useGetAgentsQuery({});

  const [sessionDialogOpen, setSessionDialogOpen] = useState(false);
  const [newSessionTitle, setNewSessionTitle] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [agentMenuAnchor, setAgentMenuAnchor] = useState<null | HTMLElement>(null);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  // WMS Categories with agents
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

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Create new session
  const handleCreateSession = async () => {
    if (!newSessionTitle.trim()) return;

    try {
      const result = await createSessionMutation({
        title: newSessionTitle,
        category: selectedCategory,
        agentId: selectedAgent?.id,
      }).unwrap();

      dispatch(createSession({ title: newSessionTitle, category: selectedCategory }));
      setSessionDialogOpen(false);
      setNewSessionTitle('');
      setSelectedCategory('');

      dispatch(addNotification({
        type: 'success',
        title: 'Session Created',
        message: `New chat session "${newSessionTitle}" created`,
        autoHide: true,
        duration: 3000,
      }));
    } catch (error: any) {
      dispatch(addNotification({
        type: 'error',
        title: 'Failed to Create Session',
        message: error?.data?.message || 'Failed to create session',
        autoHide: true,
        duration: 5000,
      }));
    }
  };

  // Send message
  const handleSendMessage = async () => {
    if (!inputValue.trim() || !currentSession || isProcessing) return;

    const messageContent = inputValue.trim();
    dispatch(setInputValue(''));

    // Add user message immediately
    const userMessage = {
      id: Date.now().toString(),
      content: messageContent,
      role: 'user' as const,
      timestamp: new Date().toISOString(),
    };
    dispatch(addMessage(userMessage));

    try {
      const result = await sendMessage({
        content: messageContent,
        sessionId: currentSession.id,
        agentId: selectedAgent?.id,
        contextFiles,
      }).unwrap();

      dispatch(addMessage(result.message));
    } catch (error: any) {
      dispatch(addNotification({
        type: 'error',
        title: 'Failed to Send Message',
        message: error?.data?.message || 'Failed to send message',
        autoHide: true,
        duration: 5000,
      }));
    }
  };

  // Handle agent selection
  const handleAgentSelect = (agent: any) => {
    dispatch(selectAgent(agent));
    setAgentMenuAnchor(null);
  };

  // Toggle category expansion
  const toggleCategory = (category: string) => {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(category)) {
      newExpanded.delete(category);
    } else {
      newExpanded.add(category);
    }
    setExpandedCategories(newExpanded);
  };

  // Get agents by category
  const getAgentsByCategory = (category: string) => {
    return agentsData?.filter(agent => agent.category === category) || [];
  };

  // Handle message reaction
  const handleMessageReaction = (messageId: string, reaction: string) => {
    // Implement message reaction logic
  };

  // Render agent panel
  const renderAgentPanel = () => (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          WMS Agents
        </Typography>

        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            Selected Agent:
          </Typography>
          <Paper
            variant="outlined"
            sx={{
              p: 1,
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              cursor: 'pointer',
            }}
            onClick={(e) => setAgentMenuAnchor(e.currentTarget)}
          >
            <Avatar sx={{ width: 24, height: 24, bgcolor: 'primary.main' }}>
              <BotIcon fontSize="small" />
            </Avatar>
            <Typography variant="body2" sx={{ flexGrow: 1 }}>
              {selectedAgent?.name || 'Select an agent'}
            </Typography>
            <ExpandMoreIcon fontSize="small" />
          </Paper>
        </Box>

        <List dense>
          {wmsCategories.map((category) => {
            const agents = getAgentsByCategory(category);
            const isExpanded = expandedCategories.has(category);
            
            return (
              <React.Fragment key={category}>
                <ListItemButton onClick={() => toggleCategory(category)}>
                  <ListItemText 
                    primary={category}
                    secondary={`${agents.length} agents`}
                  />
                  {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </ListItemButton>
                
                <Collapse in={isExpanded}>
                  <List component="div" disablePadding>
                    {agents.map((agent) => (
                      <ListItemButton
                        key={agent.id}
                        sx={{ pl: 4 }}
                        selected={selectedAgent?.id === agent.id}
                        onClick={() => handleAgentSelect(agent)}
                      >
                        <ListItemIcon>
                          <Avatar sx={{ width: 24, height: 24, bgcolor: 'secondary.main' }}>
                            <BotIcon fontSize="small" />
                          </Avatar>
                        </ListItemIcon>
                        <ListItemText
                          primary={agent.name}
                          secondary={agent.description}
                        />
                      </ListItemButton>
                    ))}
                  </List>
                </Collapse>
              </React.Fragment>
            );
          })}
        </List>
      </CardContent>
    </Card>
  );

  return (
    <Box sx={{ height: 'calc(100vh - 120px)', display: 'flex' }}>
      <Grid container spacing={2} sx={{ height: '100%' }}>
        {/* Left Sidebar - Sessions & Agents */}
        <Grid item xs={12} md={3} sx={{ height: '100%' }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 2 }}>
            {/* Session Controls */}
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Typography variant="h6">Chat Sessions</Typography>
                  <Button
                    size="small"
                    startIcon={<AddIcon />}
                    onClick={() => setSessionDialogOpen(true)}
                  >
                    New
                  </Button>
                </Box>

                <List dense>
                  {sessions.slice(0, 5).map((session) => (
                    <ListItemButton
                      key={session.id}
                      selected={currentSession?.id === session.id}
                      onClick={() => dispatch(switchSession(session.id))}
                    >
                      <ListItemText
                        primary={session.title}
                        secondary={session.category}
                      />
                    </ListItemButton>
                  ))}
                </List>
              </CardContent>
            </Card>

            {/* Agent Panel */}
            {showAgentPanel && (
              <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
                {renderAgentPanel()}
              </Box>
            )}
          </Box>
        </Grid>

        {/* Main Chat Area */}
        <Grid item xs={12} md={showContextFiles ? 6 : 9} sx={{ height: '100%' }}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {/* Chat Header */}
            <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box>
                  <Typography variant="h6">
                    {currentSession?.title || 'WMS Chatbot'}
                  </Typography>
                  {selectedAgent && (
                    <Typography variant="caption" color="text.secondary">
                      Agent: {selectedAgent.name} • Category: {selectedAgent.category}
                    </Typography>
                  )}
                </Box>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <IconButton
                    size="small"
                    onClick={() => dispatch(updateChatbotUI({ 
                      showContextFiles: !showContextFiles 
                    }))}
                  >
                    <Badge badgeContent={contextFiles.length} color="primary">
                      <FolderIcon />
                    </Badge>
                  </IconButton>
                  <IconButton size="small">
                    <SettingsIcon />
                  </IconButton>
                </Box>
              </Box>
            </Box>

            {/* Messages Area */}
            <Box sx={{ flexGrow: 1, overflow: 'auto', p: 2 }}>
              {!currentSession ? (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <BotIcon sx={{ fontSize: 64, color: 'grey.400', mb: 2 }} />
                  <Typography variant="h6" color="text.secondary" gutterBottom>
                    Welcome to WMS Chatbot
                  </Typography>
                  <Typography variant="body2" color="text.secondary" paragraph>
                    Start a new conversation or select an existing session to begin.
                  </Typography>
                  <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={() => setSessionDialogOpen(true)}
                  >
                    Start New Chat
                  </Button>
                </Box>
              ) : messages.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <Typography variant="body1" color="text.secondary" gutterBottom>
                    No messages yet. Start the conversation!
                  </Typography>
                  {selectedAgent && (
                    <Typography variant="body2" color="text.secondary">
                      You're chatting with {selectedAgent.name} ({selectedAgent.category})
                    </Typography>
                  )}
                </Box>
              ) : (
                <Box>
                  {messages.map((message) => (
                    <MessageComponent
                      key={message.id}
                      message={message}
                      onReaction={handleMessageReaction}
                    />
                  ))}
                  {isProcessing && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
                      <Avatar sx={{ bgcolor: 'secondary.main', width: 32, height: 32 }}>
                        <BotIcon />
                      </Avatar>
                      <Paper sx={{ p: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <CircularProgress size={16} />
                          <Typography variant="body2">
                            {selectedAgent?.name || 'Agent'} is thinking...
                          </Typography>
                        </Box>
                      </Paper>
                    </Box>
                  )}
                  <div ref={messagesEndRef} />
                </Box>
              )}
            </Box>

            {/* Message Input */}
            <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
              <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
                <TextField
                  fullWidth
                  multiline
                  maxRows={4}
                  placeholder="Type your message..."
                  value={inputValue}
                  onChange={(e) => dispatch(setInputValue(e.target.value))}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  disabled={isProcessing || !currentSession}
                />
                <IconButton>
                  <AttachIcon />
                </IconButton>
                <Button
                  variant="contained"
                  endIcon={<SendIcon />}
                  onClick={handleSendMessage}
                  disabled={!inputValue.trim() || isProcessing || !currentSession}
                >
                  Send
                </Button>
              </Box>
            </Box>
          </Card>
        </Grid>

        {/* Right Sidebar - Context Files */}
        {showContextFiles && (
          <Grid item xs={12} md={3} sx={{ height: '100%' }}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Context Files
                </Typography>
                
                {contextFiles.length === 0 ? (
                  <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ py: 2 }}>
                    No context files added
                  </Typography>
                ) : (
                  <List dense>
                    {contextFiles.map((fileId) => (
                      <ListItem
                        key={fileId}
                        secondaryAction={
                          <IconButton
                            edge="end"
                            size="small"
                            onClick={() => dispatch(removeContextFile(fileId))}
                          >
                            <CloseIcon fontSize="small" />
                          </IconButton>
                        }
                      >
                        <ListItemIcon>
                          <FolderIcon />
                        </ListItemIcon>
                        <ListItemText primary={`File ${fileId}`} />
                      </ListItem>
                    ))}
                  </List>
                )}

                <Button
                  fullWidth
                  variant="outlined"
                  startIcon={<AddIcon />}
                  sx={{ mt: 2 }}
                >
                  Add Files
                </Button>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>

      {/* New Session Dialog */}
      <Dialog open={sessionDialogOpen} onClose={() => setSessionDialogOpen(false)}>
        <DialogTitle>Start New Chat Session</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Session Title"
            value={newSessionTitle}
            onChange={(e) => setNewSessionTitle(e.target.value)}
            margin="normal"
            autoFocus
          />
          <FormControl fullWidth margin="normal">
            <InputLabel>WMS Category</InputLabel>
            <Select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              label="WMS Category"
            >
              {wmsCategories.map((category) => (
                <MenuItem key={category} value={category}>
                  {category}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSessionDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleCreateSession}
            variant="contained"
            disabled={!newSessionTitle.trim()}
          >
            Create Session
          </Button>
        </DialogActions>
      </Dialog>

      {/* Agent Selection Menu */}
      <Menu
        anchorEl={agentMenuAnchor}
        open={Boolean(agentMenuAnchor)}
        onClose={() => setAgentMenuAnchor(null)}
      >
        {agentsData?.slice(0, 10).map((agent) => (
          <MenuItem key={agent.id} onClick={() => handleAgentSelect(agent)}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Avatar sx={{ width: 24, height: 24, bgcolor: 'secondary.main' }}>
                <BotIcon fontSize="small" />
              </Avatar>
              <Box>
                <Typography variant="body2">{agent.name}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {agent.category}
                </Typography>
              </Box>
            </Box>
          </MenuItem>
        ))}
      </Menu>
    </Box>
  );
};

export default ChatbotPage;