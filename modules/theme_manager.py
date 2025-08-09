from tkinter import ttk
import tkinter as tk

class ThemeManager:
    """Manage application theme and styling"""
    
    # Color scheme
    COLORS = {
        'primary': '#2196F3',  # Blue
        'secondary': '#757575',  # Gray
        'success': '#4CAF50',  # Green
        'warning': '#FFC107',  # Amber
        'error': '#F44336',  # Red
        'background': '#F5F5F5',  # Light gray
        'surface': '#FFFFFF',  # White
        'text': '#212121',  # Dark gray
        'text_secondary': '#757575',  # Medium gray
        'border': '#E0E0E0',  # Light gray
        'hover': '#E3F2FD',  # Light blue
        'selected': '#BBDEFB',  # Lighter blue
        'disabled': '#BDBDBD',  # Gray
        
        # Group colors (light pastel shades)
        'group_blue': '#E3F2FD',    # Light blue background
        'group_green': '#E8F5E9',   # Light green background
        'group_purple': '#F3E5F5',  # Light purple background
        'group_orange': '#FFF3E0',  # Light orange background
    }
    
    @classmethod
    def setup_theme(cls):
        """Setup application theme"""
        style = ttk.Style()
        
        # Configure base theme
        style.configure('.',
            background=cls.COLORS['background'],
            foreground=cls.COLORS['text'],
            troughcolor=cls.COLORS['border'],
            selectbackground=cls.COLORS['primary'],
            selectforeground=cls.COLORS['surface'],
            fieldbackground=cls.COLORS['surface'],
            font=('Segoe UI', 10)
        )
        
        # Frame styles
        style.configure('Group.TFrame',
            background=cls.COLORS['surface'],
            relief='solid',
            borderwidth=1
        )
        
        # Label styles
        style.configure('Title.TLabel',
            font=('Segoe UI', 16, 'bold'),
            foreground=cls.COLORS['primary']
        )
        
        style.configure('Subtitle.TLabel',
            font=('Segoe UI', 12),
            foreground=cls.COLORS['text_secondary']
        )
        
        # Button styles
        style.configure('Primary.TButton',
            background=cls.COLORS['primary'],
            foreground=cls.COLORS['surface']
        )
        
        style.configure('Secondary.TButton',
            background=cls.COLORS['secondary'],
            foreground=cls.COLORS['surface']
        )
        
        style.configure('Success.TButton',
            background=cls.COLORS['success'],
            foreground=cls.COLORS['surface']
        )
        
        # Entry styles
        style.configure('Search.TEntry',
            fieldbackground=cls.COLORS['surface'],
            borderwidth=1,
            relief='solid'
        )
        
        # Notebook styles
        style.configure('TNotebook',
            background=cls.COLORS['background'],
            tabmargins=[2, 5, 2, 0]
        )
        
        style.configure('TNotebook.Tab',
            padding=[10, 5],
            background=cls.COLORS['surface']
        )
        
        style.map('TNotebook.Tab',
            background=[('selected', cls.COLORS['primary'])],
            foreground=[('selected', cls.COLORS['surface'])]
        )
        
        # Treeview styles
        style.configure('Treeview',
            background=cls.COLORS['surface'],
            fieldbackground=cls.COLORS['surface'],
            foreground=cls.COLORS['text']
        )
        
        style.map('Treeview',
            background=[('selected', cls.COLORS['primary'])],
            foreground=[('selected', cls.COLORS['surface'])]
        )
        
        # Group frame styles
        style.configure('BlueGroup.TLabelframe',
            background=cls.COLORS['group_blue']
        )
        
        style.configure('GreenGroup.TLabelframe',
            background=cls.COLORS['group_green']
        )
        
        style.configure('PurpleGroup.TLabelframe',
            background=cls.COLORS['group_purple']
        )
        
        style.configure('OrangeGroup.TLabelframe',
            background=cls.COLORS['group_orange']
        )
        
        # Configure labelframe label styles
        style.configure('BlueGroup.TLabelframe.Label',
            background=cls.COLORS['group_blue'],
            font=('Segoe UI', 10, 'bold')
        )
        
        style.configure('GreenGroup.TLabelframe.Label',
            background=cls.COLORS['group_green'],
            font=('Segoe UI', 10, 'bold')
        )
        
        style.configure('PurpleGroup.TLabelframe.Label',
            background=cls.COLORS['group_purple'],
            font=('Segoe UI', 10, 'bold')
        )
        
        style.configure('OrangeGroup.TLabelframe.Label',
            background=cls.COLORS['group_orange'],
            font=('Segoe UI', 10, 'bold')
        )
    
    @classmethod
    def get_color(cls, name: str) -> str:
        """Get color by name"""
        return cls.COLORS.get(name, cls.COLORS['primary'])