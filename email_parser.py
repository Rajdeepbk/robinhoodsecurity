import email
from email import policy
from typing import Dict, Any

class EmailParser:
    def parse_email(self, raw_email: str) -> Dict[str, Any]:
        """Parse raw email content and extract relevant information."""
        msg = email.message_from_string(raw_email, policy=policy.default)
        
        content = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    content += part.get_content()
        else:
            content = msg.get_content()
            
        return {
            'subject': msg['subject'] or '',
            'from': msg['from'] or '',
            'date': msg['date'] or '',
            'content': content.strip(),
            'source': 'email'
        }
