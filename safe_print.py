#!/usr/bin/env python3
"""
Windows-compatible emoji replacement for console output
"""

def safe_print(message):
    """Print message with emoji replacement for Windows compatibility"""
    # Replace Unicode emojis with ASCII equivalents
    replacements = {
        '🚀': '>>', 
        '📊': '[DATA]',
        '📈': '[LONG]', 
        '📉': '[SHORT]',
        '🎯': '[OPT]',
        '💰': '[PROFIT]',
        '📅': '[DATE]',
        '💾': '[SAVE]',
        '🔍': '[SEARCH]',
        '✅': '[OK]',
        '❌': '[FAIL]',
        '⚠️': '[WARN]',
        '🔄': '[CYCLE]',
        '📝': '[LOG]',
        '🎉': '[SUCCESS]',
        '🛡️': '[STOP]',
        '📤': '[EXIT]',
        '📥': '[ENTRY]'
    }
    
    for emoji, replacement in replacements.items():
        message = message.replace(emoji, replacement)
    
    try:
        print(message)
    except UnicodeEncodeError:
        # Fallback: encode to ASCII, ignoring problematic characters
        safe_message = message.encode('ascii', 'ignore').decode('ascii')
        print(safe_message)

if __name__ == "__main__":
    # Test the safe print function
    safe_print("🚀 Testing safe print with emojis 📊 📈 📉")
    safe_print("Regular text without emojis")
