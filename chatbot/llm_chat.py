"""
LLM Step Helper - An AI assistant that helps students understand calculus steps.

Talks to any OpenAI-compatible chat-completions endpoint. Defaults to a local
Ollama server; in production we point this at the self-hosted Ollama on the
Hetzner box via env vars.

Env vars:
  LLM_BASE_URL  e.g. http://localhost:11434/v1
  LLM_API_KEY   bearer token (optional for local Ollama)
  LLM_MODEL     e.g. qwen2.5:7b
"""

import os
import re
import requests


# System prompt that constrains the LLM to calculus topics only
SYSTEM_PROMPT = """You are Calaun, a friendly calculus tutor. Help students understand derivatives, integrals, and limits.

STYLE RULES:
- Be concise. No filler phrases like "Does this make sense?" or "Do you have questions?"
- ALWAYS wrap LaTeX in proper delimiters: \\( ... \\) for inline math, \\[ ... \\] for display math
- NEVER use bare LaTeX like \\frac without delimiters - ALWAYS wrap it!
- One short paragraph max, then show the general formula
- Be warm but brief

LATEX FORMATTING (CRITICAL):
- Inline: "The derivative \\( \\frac{dy}{dx} \\) represents..."
- Display: "The power rule is: \\[ \\frac{d}{dx} x^n = n \\cdot x^{n-1} \\]"
- WRONG: "\\frac{1}{2}" (missing delimiters!)
- RIGHT: "\\( \\frac{1}{2} \\)" or "\\[ \\frac{1}{2} \\]"

CRITICAL - DO NOT CALCULATE:
- NEVER compute numerical answers, evaluate expressions, or solve problems
- NEVER state what a limit, derivative, or integral equals
- If asked "what is the answer" or for any specific calculation, say: "Check the steps above for the answer, or type a new expression in the search box!"
- You explain CONCEPTS and RULES only - the solver does all calculations
- If steps are shown, refer to them but don't recalculate or verify numbers

EXAMPLE GOOD RESPONSE for "what's the power rule?":
"The **power rule**: bring down the exponent, then subtract 1.

\\[ \\frac{d}{dx} x^n = n \\cdot x^{n-1} \\]"

EXAMPLE BAD RESPONSE (never do this):
"The answer is 5" or "The limit equals 2" or "2x^2 + 3 gives us..."

SCOPE:
- Only answer calculus questions
- If off-topic, say: "I'm here to help with calculus! Ask me about derivatives, integrals, or limits."
- Explain the general concept/rule, never the specific numerical result"""


DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5:7b"


class LLMStepHelper:
    """An LLM-based assistant that helps students understand calculus solution steps."""

    def __init__(self, api_key=None, model=None, base_url=None):
        self.api_key = api_key or os.environ.get('LLM_API_KEY', '')
        self.model = model or os.environ.get('LLM_MODEL', DEFAULT_MODEL)
        base = (base_url or os.environ.get('LLM_BASE_URL', DEFAULT_BASE_URL)).rstrip('/')
        self.api_url = f"{base}/chat/completions"
        
        # Keywords for calculus topic detection
        self.calculus_keywords = {
            'derivative', 'integral', 'limit', 'differentiate', 'integrate',
            'calculus', 'chain rule', 'power rule', 'product rule',
            'quotient rule', 'substitution', 'integration by parts',
            'antiderivative', 'slope', 'tangent',
            'rate of change', 'continuous', 'lhopital', "l'hopital",
            'indeterminate', 'infinity', 'converge', 'diverge',
            'theorem', 'proof', 'dx', 'dy', 'sin(', 'cos(', 'tan(',
            'log(', 'ln(', 'exp(',
        }
    
    def _is_calculus_related(self, message, has_steps=False):
        """
        Check if the message is related to calculus or the current problem.
        
        Args:
            message: The user's message
            has_steps: Whether solution steps are provided as context
            
        Returns:
            True if the message seems calculus-related
        """
        message_lower = message.lower()
        
        # If we have steps and they're asking about them, it's valid
        if has_steps:
            step_references = ['step', 'this', 'that', 'here', 'above', 'why', 'how', 'what']
            if any(ref in message_lower for ref in step_references):
                return True
        
        # Check for calculus keywords
        for keyword in self.calculus_keywords:
            if keyword in message_lower:
                return True
        
        # Check for math patterns (numbers, operators, variables)
        math_pattern = r'[xyz]\s*[\+\-\*\/\^]|d[xy]|∫|\d+\s*[\+\-\*\/\^]'
        if re.search(math_pattern, message_lower):
            return True
        
        return False
    
    def _format_steps_context(self, steps_html):
        """
        Extract readable text from HTML steps for context.
        
        Args:
            steps_html: HTML content of the solution steps
            
        Returns:
            Plain text representation of the steps
        """
        if not steps_html:
            return ""
        
        # Remove HTML tags but preserve structure
        text = re.sub(r'<script[^>]*>.*?</script>', '', steps_html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        
        # Convert common elements to readable format
        text = re.sub(r'<h\d[^>]*>', '\n## ', text)
        text = re.sub(r'</h\d>', '\n', text)
        text = re.sub(r'<li[^>]*>', '\n• ', text)
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<p[^>]*>', '\n', text)
        text = re.sub(r'</p>', '\n', text)
        
        # Preserve LaTeX delimiters
        text = re.sub(r'\\$$', r'\\(', text)
        text = re.sub(r'\\$$', r'\\)', text)
        text = re.sub(r'\\\[', r'\\[', text)
        text = re.sub(r'\\\]', r'\\]', text)
        
        # Remove remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = text.strip()
        
        return text
    
    def get_response(self, message, steps_html=None, conversation_history=None):
        """
        Get a response from the LLM.
        
        Args:
            message: The user's question
            steps_html: Optional HTML content of the current solution steps
            conversation_history: Optional list of previous messages
            
        Returns:
            The assistant's response text
        """
        has_steps = bool(steps_html)

        # Check if the question is calculus-related
        if not self._is_calculus_related(message, has_steps):
            return (
                "I'm here to help with calculus! Feel free to ask me about "
                "derivatives, integrals, limits, or any of the steps shown above."
            )
        
        # Build the messages list
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Add steps context if available
        if steps_html:
            steps_text = self._format_steps_context(steps_html)
            if steps_text:
                context_msg = (
                    f"The student is looking at the following solution steps:\n\n"
                    f"---\n{steps_text}\n---\n\n"
                    f"Help them understand these steps if they ask about them."
                )
                messages.append({"role": "system", "content": context_msg})
        
        # Add conversation history if provided
        if conversation_history:
            for entry in conversation_history[-10:]:  # Keep last 10 messages
                messages.append({
                    "role": entry.get("role", "user"),
                    "content": entry.get("content", "")
                })
        
        # Add the current message
        messages.append({"role": "user", "content": message})
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.7,
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            return "The response is taking too long. Please try again."
        except requests.exceptions.RequestException as e:
            print(f"LLM API error: {e}")
            return (
                "I'm having trouble connecting right now. "
                "Please try again in a moment."
            )


# Singleton instance
_llm_helper = None


def get_llm_helper():
    """Get or create the LLM helper instance."""
    global _llm_helper
    if _llm_helper is None:
        _llm_helper = LLMStepHelper()
    return _llm_helper


def llm_response(message, steps_html=None, conversation_history=None):
    """
    Get an LLM response for the given message.
    
    Args:
        message: The user's question
        steps_html: Optional HTML content of current solution steps
        conversation_history: Optional list of previous messages
        
    Returns:
        The assistant's response
    """
    helper = get_llm_helper()
    return helper.get_response(message, steps_html, conversation_history)
