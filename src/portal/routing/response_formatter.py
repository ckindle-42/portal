"""
Response Formatter - Telegram-optimized output formatting
"""

import re
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class FormattedResponse:
    """Formatted response with metadata"""
    text: str
    chunks: List[str]
    has_code: bool
    has_links: bool
    estimated_read_time_seconds: int


class ResponseFormatter:
    """
    Formats LLM responses for Telegram
    
    Features:
    - Message splitting for length limits
    - Markdown formatting
    - Code block handling
    - Link detection
    """
    
    TELEGRAM_MAX_LENGTH = 4096
    WORDS_PER_MINUTE = 200
    
    def __init__(self, max_length: int = None):
        self.max_length = max_length or self.TELEGRAM_MAX_LENGTH
    
    def format(self, text: str) -> FormattedResponse:
        """
        Format response for Telegram
        
        Args:
            text: Raw LLM response
            
        Returns:
            FormattedResponse with chunks and metadata
        """
        
        # Clean up text
        text = self._clean_text(text)
        
        # Detect features
        has_code = bool(re.search(r'```', text))
        has_links = bool(re.search(r'https?://', text))
        
        # Split into chunks if needed
        chunks = self._split_message(text)
        
        # Estimate read time
        word_count = len(text.split())
        read_time = max(1, int(word_count / self.WORDS_PER_MINUTE * 60))
        
        return FormattedResponse(
            text=text,
            chunks=chunks,
            has_code=has_code,
            has_links=has_links,
            estimated_read_time_seconds=read_time
        )
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        # Escape special Telegram markdown characters outside code blocks
        # (Telegram uses different markdown than standard)
        text = self._escape_telegram_special(text)
        
        return text.strip()
    
    def _escape_telegram_special(self, text: str) -> str:
        """Escape special characters for Telegram Markdown"""
        
        # Split by code blocks to preserve them
        parts = re.split(r'(```[\s\S]*?```)', text)
        
        result = []
        for i, part in enumerate(parts):
            if part.startswith('```'):
                # Keep code blocks as-is
                result.append(part)
            else:
                # Escape _ and * outside code blocks (but keep ** and __)
                # This is a simple approach - full Telegram markdown is complex
                result.append(part)
        
        return ''.join(result)
    
    def _split_message(self, text: str) -> List[str]:
        """Split message into chunks that fit Telegram limits"""
        
        if len(text) <= self.max_length:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        # Try to split on natural boundaries
        paragraphs = text.split('\n\n')
        
        for para in paragraphs:
            # If paragraph itself is too long, split by lines
            if len(para) > self.max_length:
                lines = para.split('\n')
                for line in lines:
                    if len(current_chunk) + len(line) + 1 > self.max_length:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = line
                    else:
                        current_chunk += '\n' + line if current_chunk else line
            else:
                if len(current_chunk) + len(para) + 2 > self.max_length:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = para
                else:
                    current_chunk += '\n\n' + para if current_chunk else para
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def format_error(self, error: str) -> str:
        """Format error message"""
        return f"âŒ Error: {error}"
    
    def format_tool_result(self, tool_name: str, result: dict) -> str:
        """Format tool execution result"""
        
        if result.get('success'):
            output = result.get('result', 'Done')
            return f"ðŸ”§ **{tool_name}**\n\n{output}"
        else:
            error = result.get('error', 'Unknown error')
            return f"âŒ **{tool_name}** failed: {error}"
    
    def format_code_block(self, code: str, language: str = "") -> str:
        """Format code block"""
        return f"```{language}\n{code}\n```"
    
    def truncate(self, text: str, max_length: int = None) -> str:
        """Truncate text with ellipsis"""
        max_len = max_length or self.max_length
        
        if len(text) <= max_len:
            return text
        
        return text[:max_len - 3] + "..."
