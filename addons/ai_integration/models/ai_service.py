# -*- coding: utf-8 -*-
"""
AI Service - Core OpenAI Integration
=====================================
Cung cấp các phương thức gọi OpenAI API dùng chung cho toàn hệ thống.
Bao gồm: chat completion, embeddings, retry logic, error handling, token counting.
"""

import json
import time
import hashlib
import logging
from datetime import datetime

from odoo import models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Try importing OpenAI
try:
    import openai
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    _logger.warning("OpenAI library not installed. Run: pip install openai")

# Try importing tiktoken for token counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    _logger.warning("tiktoken library not installed. Token counting will be estimated.")


class AIService(models.AbstractModel):
    """
    AI Service - Abstract model providing OpenAI API integration.
    
    Usage:
        ai_service = self.env['ai.service']
        result = ai_service.chat_completion(prompt="Hello", system_prompt="You are helpful")
        summary = ai_service.summarize_text(text, max_words=100)
        extracted = ai_service.extract_structured_data(text, schema)
    """
    _name = 'ai.service'
    _description = 'AI Service - OpenAI Integration'

    # ==================== CONFIGURATION ====================
    
    def _get_api_key(self):
        """Get OpenAI API key from system parameters."""
        api_key = self.env['ir.config_parameter'].sudo().get_param('ai_integration.openai_api_key', '')
        if not api_key:
            raise UserError(_("OpenAI API Key chưa được cấu hình. Vui lòng vào Settings > AI Integration để thiết lập."))
        return api_key.strip()
    
    def _get_config(self):
        """Get AI configuration from system parameters."""
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'api_key': ICP.get_param('ai_integration.openai_api_key', ''),
            'model': ICP.get_param('ai_integration.openai_model', 'gpt-4o-mini'),
            'max_tokens': int(ICP.get_param('ai_integration.max_tokens', '2000')),
            'temperature': float(ICP.get_param('ai_integration.temperature', '0.3')),
            'timeout': int(ICP.get_param('ai_integration.timeout', '60')),
            'max_retries': int(ICP.get_param('ai_integration.max_retries', '3')),
            'log_enabled': ICP.get_param('ai_integration.log_enabled', 'True') == 'True',
            'cache_enabled': ICP.get_param('ai_integration.cache_enabled', 'True') == 'True',
            'cache_ttl': int(ICP.get_param('ai_integration.cache_ttl', '3600')),
        }
    
    def _get_client(self):
        """Get OpenAI client instance."""
        if not OPENAI_AVAILABLE:
            raise UserError(_("Thư viện OpenAI chưa được cài đặt. Chạy: pip install openai"))
        
        api_key = self._get_api_key()
        config = self._get_config()
        # Disable SDK internal retries; we handle retries explicitly in service methods.
        return OpenAI(api_key=api_key, max_retries=0, timeout=config.get('timeout', 60))

    # ==================== TOKEN COUNTING ====================
    
    def count_tokens(self, text, model=None):
        """Count tokens in text using tiktoken or estimation."""
        if not text:
            return 0
        
        if not model:
            model = self._get_config().get('model', 'gpt-4o-mini')
        
        if TIKTOKEN_AVAILABLE:
            try:
                # Map model names to encoding
                if 'gpt-4' in model:
                    encoding = tiktoken.encoding_for_model('gpt-4')
                else:
                    encoding = tiktoken.encoding_for_model('gpt-3.5-turbo')
                return len(encoding.encode(text))
            except Exception:
                pass
        
        # Fallback: estimate ~4 chars per token for English, ~2 for Vietnamese
        return len(text) // 2
    
    def estimate_cost(self, input_tokens, output_tokens, model=None):
        """Estimate cost in USD based on token usage."""
        if not model:
            model = self._get_config().get('model', 'gpt-4o-mini')
        
        # Pricing per 1M tokens (as of 2024)
        pricing = {
            'gpt-4o': {'input': 2.50, 'output': 10.00},
            'gpt-4o-mini': {'input': 0.15, 'output': 0.60},
            'gpt-4-turbo': {'input': 10.00, 'output': 30.00},
            'gpt-4': {'input': 30.00, 'output': 60.00},
            'gpt-3.5-turbo': {'input': 0.50, 'output': 1.50},
        }
        
        # Find matching pricing
        price = pricing.get(model, pricing['gpt-4o-mini'])
        
        cost = (input_tokens * price['input'] + output_tokens * price['output']) / 1_000_000
        return round(cost, 6)

    # ==================== CACHING ====================
    
    def _get_cache_key(self, prompt, system_prompt, model):
        """Generate cache key from prompt."""
        content = f"{model}:{system_prompt}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _get_cached_response(self, cache_key):
        """Get cached response if available and not expired."""
        config = self._get_config()
        if not config['cache_enabled']:
            return None
        
        cache = self.env['ai.cache'].sudo().search([
            ('cache_key', '=', cache_key),
            ('expires_at', '>', datetime.now())
        ], limit=1)
        
        if cache:
            cache.hit_count += 1
            return cache.response
        return None
    
    def _set_cached_response(self, cache_key, response, prompt_hash=None):
        """Cache response for future use."""
        config = self._get_config()
        if not config['cache_enabled']:
            return
        
        from datetime import timedelta
        expires_at = datetime.now() + timedelta(seconds=config['cache_ttl'])
        
        # Check if cache entry already exists - update instead of create
        existing = self.env['ai.cache'].sudo().search([('cache_key', '=', cache_key)], limit=1)
        if existing:
            existing.write({
                'response': response,
                'expires_at': expires_at,
                'prompt_hash': prompt_hash or cache_key[:64],
            })
        else:
            try:
                self.env['ai.cache'].sudo().create({
                    'cache_key': cache_key,
                    'prompt_hash': prompt_hash or cache_key[:64],
                    'response': response,
                    'expires_at': expires_at,
                })
            except Exception:
                # If duplicate key error, ignore - cache is optional
                pass

    # ==================== LOGGING ====================
    
    def _log_request(self, **kwargs):
        """Log AI request for audit and monitoring."""
        config = self._get_config()
        if not config['log_enabled']:
            return None
        
        try:
            log = self.env['ai.log'].sudo().create({
                'user_id': self.env.uid,
                'model_name': kwargs.get('model_name', ''),
                'record_id': kwargs.get('record_id', 0),
                'action_type': kwargs.get('action_type', 'chat'),
                'ai_model': kwargs.get('ai_model', config['model']),
                'prompt_preview': (kwargs.get('prompt', '')[:500] + '...') if len(kwargs.get('prompt', '')) > 500 else kwargs.get('prompt', ''),
                'response_preview': (kwargs.get('response', '')[:500] + '...') if len(kwargs.get('response', '')) > 500 else kwargs.get('response', ''),
                'input_tokens': kwargs.get('input_tokens', 0),
                'output_tokens': kwargs.get('output_tokens', 0),
                'total_tokens': kwargs.get('input_tokens', 0) + kwargs.get('output_tokens', 0),
                'cost_usd': kwargs.get('cost_usd', 0),
                'latency_ms': kwargs.get('latency_ms', 0),
                'status': kwargs.get('status', 'success'),
                'error_message': kwargs.get('error_message', ''),
            })
            return log
        except Exception as e:
            _logger.error(f"Failed to log AI request: {e}")
            return None

    # ==================== CORE API CALLS ====================

    def chat_completion_with_tools(
        self,
        messages,
        tools=None,
        model=None,
        temperature=None,
        max_tokens=None,
        tool_choice='auto',
        model_name=None,
        record_id=None,
        action_type='chat',
    ):
        """Call OpenAI Chat Completions with optional tool calling.

        This method returns a structured dict (success/data/error) used by
        `ai.chat.orchestrator`.

        Args:
            messages: List[Dict] OpenAI chat messages
            tools: Optional[List[Dict]] tools schema in OpenAI format
            model, temperature, max_tokens: override config
            tool_choice: 'auto' | 'none' | {'type':'function','function':{'name':...}}

        Returns:
            {
              'success': bool,
              'data': {
                 'message': {'role': 'assistant', 'content': str, 'tool_calls': [...]?},
                 'usage': {'prompt_tokens': int, 'completion_tokens': int, 'total_tokens': int},
                 'model': str,
              },
              'error': str (if any)
            }
        """
        if not OPENAI_AVAILABLE:
            return {
                'success': False,
                'error': _("Thư viện OpenAI chưa được cài đặt. Chạy: pip install openai"),
            }

        config = self._get_config()
        model = model or config['model']
        temperature = temperature if temperature is not None else config['temperature']
        max_tokens = max_tokens or config['max_tokens']

        start_time = time.time()
        status = 'success'
        error_message = ''
        response_message = {'role': 'assistant', 'content': ''}
        usage_info = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

        # Build a compact prompt/response preview for logging
        prompt_preview = ''
        try:
            prompt_preview = json.dumps(messages[-3:], ensure_ascii=False)
        except Exception:
            prompt_preview = str(messages[-1]) if messages else ''

        for attempt in range(config['max_retries']):
            try:
                client = self._get_client()

                kwargs = {
                    'model': model,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens,
                    'timeout': config['timeout'],
                }

                if tools:
                    kwargs['tools'] = tools
                    if tool_choice is not None:
                        kwargs['tool_choice'] = tool_choice

                response = client.chat.completions.create(**kwargs)

                msg = response.choices[0].message
                response_message = {
                    'role': getattr(msg, 'role', 'assistant') or 'assistant',
                    'content': (getattr(msg, 'content', None) or ''),
                }

                tool_calls = getattr(msg, 'tool_calls', None)
                if tool_calls:
                    normalized_calls = []
                    for tc in tool_calls:
                        fn = getattr(tc, 'function', None)
                        normalized_calls.append({
                            'id': getattr(tc, 'id', None),
                            'type': getattr(tc, 'type', 'function'),
                            'function': {
                                'name': getattr(fn, 'name', None) if fn else None,
                                'arguments': getattr(fn, 'arguments', None) if fn else None,
                            },
                        })
                    response_message['tool_calls'] = normalized_calls

                if getattr(response, 'usage', None):
                    usage_info = {
                        'prompt_tokens': response.usage.prompt_tokens or 0,
                        'completion_tokens': response.usage.completion_tokens or 0,
                        'total_tokens': response.usage.total_tokens or 0,
                    }
                else:
                    # Fallback estimates
                    joined = ''
                    try:
                        joined = json.dumps(messages, ensure_ascii=False)
                    except Exception:
                        joined = str(messages)
                    prompt_tokens = self.count_tokens(joined, model)
                    completion_tokens = self.count_tokens(response_message.get('content', ''), model)
                    usage_info = {
                        'prompt_tokens': prompt_tokens,
                        'completion_tokens': completion_tokens,
                        'total_tokens': prompt_tokens + completion_tokens,
                    }

                break

            except Exception as e:
                error_message = str(e)
                _logger.warning(f"OpenAI API attempt {attempt + 1} failed: {e}")
                if attempt < config['max_retries'] - 1:
                    wait_time = (2 ** attempt) + 1
                    time.sleep(wait_time)
                else:
                    status = 'error'

        latency_ms = int((time.time() - start_time) * 1000)
        cost_usd = 0
        try:
            cost_usd = self.estimate_cost(
                usage_info.get('prompt_tokens', 0),
                usage_info.get('completion_tokens', 0),
                model,
            )
        except Exception:
            cost_usd = 0

        # Log request
        try:
            self._log_request(
                model_name=model_name,
                record_id=record_id,
                action_type=action_type,
                ai_model=model,
                prompt=prompt_preview,
                response=response_message.get('content', ''),
                input_tokens=usage_info.get('prompt_tokens', 0),
                output_tokens=usage_info.get('completion_tokens', 0),
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                status=status,
                error_message=error_message,
            )
        except Exception:
            pass

        if status != 'success':
            return {
                'success': False,
                'error': error_message or _('Lỗi gọi OpenAI API'),
            }

        return {
            'success': True,
            'data': {
                'message': response_message,
                'usage': usage_info,
                'model': model,
            }
        }
    
    def chat_completion(self, prompt, system_prompt=None, model=None, temperature=None, 
                        max_tokens=None, json_mode=False, use_cache=True,
                        model_name=None, record_id=None, action_type='chat'):
        """
        Call OpenAI Chat Completion API.
        
        Args:
            prompt: User message/prompt
            system_prompt: System instruction (optional)
            model: Model to use (default from config)
            temperature: Creativity level 0-2 (default from config)
            max_tokens: Max response tokens (default from config)
            json_mode: If True, force JSON response
            use_cache: If True, use caching
            model_name: Odoo model name for logging
            record_id: Record ID for logging
            action_type: Type of action for logging
            
        Returns:
            str: AI response text
        """
        config = self._get_config()
        model = model or config['model']
        temperature = temperature if temperature is not None else config['temperature']
        max_tokens = max_tokens or config['max_tokens']
        
        # Default system prompt
        if not system_prompt:
            system_prompt = """Bạn là trợ lý AI thông minh trong hệ thống quản lý doanh nghiệp Odoo.
Bạn hỗ trợ người dùng với các tác vụ liên quan đến văn bản, nhân sự và khách hàng.
Trả lời bằng tiếng Việt, ngắn gọn, chính xác và chuyên nghiệp.
Nếu không chắc chắn, hãy nói rõ và đề xuất cách xác minh."""
        
        # Check cache
        if use_cache:
            cache_key = self._get_cache_key(prompt, system_prompt, model)
            cached = self._get_cached_response(cache_key)
            if cached:
                return cached
        
        # Prepare messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # Count input tokens
        input_tokens = self.count_tokens(system_prompt + prompt, model)
        
        # Call API with retry
        start_time = time.time()
        response_text = ""
        output_tokens = 0
        status = "success"
        error_message = ""
        
        for attempt in range(config['max_retries']):
            try:
                client = self._get_client()
                
                kwargs = {
                    'model': model,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens,
                    'timeout': config['timeout'],
                }
                
                if json_mode:
                    kwargs['response_format'] = {"type": "json_object"}
                
                response = client.chat.completions.create(**kwargs)
                
                response_text = response.choices[0].message.content
                output_tokens = response.usage.completion_tokens if response.usage else self.count_tokens(response_text, model)
                input_tokens = response.usage.prompt_tokens if response.usage else input_tokens
                
                break
                
            except Exception as e:
                error_message = str(e)
                _logger.warning(f"OpenAI API attempt {attempt + 1} failed: {e}")
                
                if attempt < config['max_retries'] - 1:
                    # Exponential backoff
                    wait_time = (2 ** attempt) + 1
                    time.sleep(wait_time)
                else:
                    status = "error"
                    raise UserError(_("Lỗi gọi OpenAI API sau %s lần thử: %s") % (config['max_retries'], error_message))
        
        latency_ms = int((time.time() - start_time) * 1000)
        cost_usd = self.estimate_cost(input_tokens, output_tokens, model)
        
        # Log request
        self._log_request(
            model_name=model_name,
            record_id=record_id,
            action_type=action_type,
            ai_model=model,
            prompt=prompt,
            response=response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
        )
        
        # Cache response
        if use_cache and status == "success":
            self._set_cached_response(cache_key, response_text)
        
        return response_text

    # ==================== HIGH-LEVEL FUNCTIONS ====================
    
    def summarize_text(self, text, max_words=150, focus=None, model_name=None, record_id=None):
        """
        Tóm tắt văn bản.
        
        Args:
            text: Văn bản cần tóm tắt
            max_words: Số từ tối đa
            focus: Điểm cần tập trung (optional)
        """
        if not text or len(text.strip()) < 50:
            return text
        
        focus_instruction = f"\nTập trung vào: {focus}" if focus else ""
        
        prompt = f"""Tóm tắt văn bản sau trong khoảng {max_words} từ.
Giữ lại thông tin quan trọng nhất.{focus_instruction}

Văn bản:
\"\"\"
{text[:8000]}
\"\"\"

Tóm tắt:"""
        
        return self.chat_completion(
            prompt=prompt,
            temperature=0.3,
            model_name=model_name,
            record_id=record_id,
            action_type='summarize'
        )
    
    def extract_structured_data(self, text, schema, instructions=None, model_name=None, record_id=None):
        """
        Trích xuất dữ liệu có cấu trúc từ văn bản.
        
        Args:
            text: Văn bản nguồn
            schema: Dict mô tả các trường cần trích xuất
            instructions: Hướng dẫn bổ sung
            
        Returns:
            dict: Dữ liệu đã trích xuất
        """
        if not text:
            return {}
        
        schema_str = json.dumps(schema, ensure_ascii=False, indent=2)
        extra = f"\n\nHướng dẫn thêm: {instructions}" if instructions else ""
        
        prompt = f"""Trích xuất thông tin từ văn bản sau theo cấu trúc JSON được chỉ định.
Chỉ trả về JSON hợp lệ, không có text bổ sung.
Nếu không tìm thấy thông tin, để giá trị null.

Cấu trúc cần trích xuất:
{schema_str}
{extra}

Văn bản:
\"\"\"
{text[:8000]}
\"\"\"

JSON kết quả:"""
        
        response = self.chat_completion(
            prompt=prompt,
            temperature=0.1,
            json_mode=True,
            model_name=model_name,
            record_id=record_id,
            action_type='extract'
        )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            return {}
    
    def classify_text(self, text, categories, model_name=None, record_id=None):
        """
        Phân loại văn bản vào các danh mục.
        
        Args:
            text: Văn bản cần phân loại
            categories: List các danh mục có thể
            
        Returns:
            dict: {'category': str, 'confidence': float, 'reason': str}
        """
        if not text or not categories:
            return {'category': None, 'confidence': 0, 'reason': 'No input'}
        
        categories_str = ", ".join(categories)
        
        prompt = f"""Phân loại văn bản sau vào MỘT trong các danh mục: {categories_str}

Trả về JSON với format:
{{"category": "<tên danh mục>", "confidence": <0-1>, "reason": "<lý do ngắn gọn>"}}

Văn bản:
\"\"\"
{text[:4000]}
\"\"\"

JSON kết quả:"""
        
        response = self.chat_completion(
            prompt=prompt,
            temperature=0.1,
            json_mode=True,
            model_name=model_name,
            record_id=record_id,
            action_type='classify'
        )
        
        try:
            result = json.loads(response)
            if result.get('category') not in categories:
                result['category'] = categories[0]
            return result
        except:
            return {'category': categories[0], 'confidence': 0.5, 'reason': 'Parse error'}
    
    def generate_content(self, template, context, tone='professional', model_name=None, record_id=None):
        """
        Sinh nội dung theo template và context.
        
        Args:
            template: Loại nội dung (email, report, contract, etc.)
            context: Dict chứa thông tin ngữ cảnh
            tone: Giọng văn (professional, friendly, formal)
        """
        context_str = "\n".join([f"- {k}: {v}" for k, v in context.items() if v])
        
        tone_instructions = {
            'professional': 'chuyên nghiệp, lịch sự',
            'friendly': 'thân thiện, gần gũi',
            'formal': 'trang trọng, nghiêm túc',
        }
        tone_desc = tone_instructions.get(tone, tone_instructions['professional'])
        
        prompt = f"""Tạo nội dung {template} với giọng văn {tone_desc}.

Thông tin ngữ cảnh:
{context_str}

Yêu cầu:
- Viết bằng tiếng Việt chuẩn
- Đầy đủ, chuyên nghiệp
- Phù hợp với ngữ cảnh doanh nghiệp

Nội dung:"""
        
        return self.chat_completion(
            prompt=prompt,
            temperature=0.5,
            model_name=model_name,
            record_id=record_id,
            action_type='generate'
        )
    
    def analyze_risk(self, text, risk_types=None, model_name=None, record_id=None):
        """
        Phân tích rủi ro trong văn bản.
        
        Args:
            text: Văn bản cần phân tích (hợp đồng, chính sách, etc.)
            risk_types: List các loại rủi ro cần kiểm tra
            
        Returns:
            dict: {'risk_score': 0-100, 'risks': [...], 'recommendations': [...]}
        """
        if not text:
            return {'risk_score': 0, 'risks': [], 'recommendations': []}
        
        default_risks = ['điều khoản phạt', 'miễn trừ trách nhiệm', 'thanh toán', 
                        'bảo mật thông tin', 'chấm dứt hợp đồng', 'tranh chấp']
        risk_types = risk_types or default_risks
        risk_str = ", ".join(risk_types)
        
        prompt = f"""Phân tích rủi ro trong văn bản sau.

Các loại rủi ro cần kiểm tra: {risk_str}

Trả về JSON với format:
{{
  "risk_score": <0-100>,
  "risks": [
    {{"type": "<loại rủi ro>", "severity": "<low/medium/high>", "description": "<mô tả>", "location": "<vị trí trong văn bản>"}}
  ],
  "recommendations": ["<đề xuất 1>", "<đề xuất 2>"]
}}

Văn bản:
\"\"\"
{text[:8000]}
\"\"\"

JSON kết quả:"""
        
        response = self.chat_completion(
            prompt=prompt,
            temperature=0.2,
            json_mode=True,
            model_name=model_name,
            record_id=record_id,
            action_type='analyze_risk'
        )
        
        try:
            return json.loads(response)
        except:
            return {'risk_score': 0, 'risks': [], 'recommendations': [], 'error': 'Parse error'}
    
    def answer_question(self, question, context, model_name=None, record_id=None):
        """
        Trả lời câu hỏi dựa trên ngữ cảnh cho trước (RAG-style).
        
        Args:
            question: Câu hỏi của người dùng
            context: Ngữ cảnh/tài liệu liên quan
            
        Returns:
            dict: {'answer': str, 'sources': [...], 'confidence': float}
        """
        if not question:
            return {'answer': '', 'sources': [], 'confidence': 0}
        
        prompt = f"""Trả lời câu hỏi dựa trên ngữ cảnh được cung cấp.
Nếu thông tin không có trong ngữ cảnh, hãy nói rõ.
Trích dẫn nguồn khi có thể.

Ngữ cảnh:
\"\"\"
{context[:10000]}
\"\"\"

Câu hỏi: {question}

Trả về JSON:
{{"answer": "<câu trả lời>", "sources": ["<trích dẫn liên quan>"], "confidence": <0-1>}}

JSON kết quả:"""
        
        response = self.chat_completion(
            prompt=prompt,
            temperature=0.3,
            json_mode=True,
            model_name=model_name,
            record_id=record_id,
            action_type='qa'
        )
        
        try:
            return json.loads(response)
        except:
            return {'answer': response, 'sources': [], 'confidence': 0.5}
    
    def translate_text(self, text, target_language='en', model_name=None, record_id=None):
        """
        Dịch văn bản.
        
        Args:
            text: Văn bản cần dịch
            target_language: Ngôn ngữ đích (vi, en, etc.)
        """
        if not text:
            return ""
        
        lang_names = {
            'vi': 'tiếng Việt',
            'en': 'tiếng Anh',
            'zh': 'tiếng Trung',
            'ja': 'tiếng Nhật',
            'ko': 'tiếng Hàn',
        }
        target_name = lang_names.get(target_language, target_language)
        
        prompt = f"""Dịch văn bản sau sang {target_name}.
Giữ nguyên định dạng, số liệu và tên riêng.
Chỉ trả về bản dịch, không thêm gì khác.

Văn bản:
\"\"\"
{text[:8000]}
\"\"\"

Bản dịch:"""
        
        return self.chat_completion(
            prompt=prompt,
            temperature=0.2,
            model_name=model_name,
            record_id=record_id,
            action_type='translate'
        )

    # ==================== UTILITIES ====================
    
    def chunk_text(self, text, max_tokens=3000, overlap=200):
        """
        Chia văn bản thành các phần nhỏ.
        
        Args:
            text: Văn bản cần chia
            max_tokens: Số token tối đa mỗi phần
            overlap: Số token overlap giữa các phần
            
        Returns:
            List[str]: Các phần văn bản
        """
        if not text:
            return []
        
        # Estimate chars per chunk (rough: 2 chars per token for Vietnamese)
        chars_per_token = 2
        max_chars = max_tokens * chars_per_token
        overlap_chars = overlap * chars_per_token
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + max_chars
            
            # Try to break at paragraph or sentence
            if end < len(text):
                # Find last paragraph break
                para_break = text.rfind('\n\n', start, end)
                if para_break > start + max_chars // 2:
                    end = para_break
                else:
                    # Find last sentence break
                    for sep in ['. ', '.\n', '? ', '! ']:
                        sent_break = text.rfind(sep, start, end)
                        if sent_break > start + max_chars // 2:
                            end = sent_break + len(sep)
                            break
            
            chunks.append(text[start:end].strip())
            start = end - overlap_chars
        
        return [c for c in chunks if c]
    
    def mask_pii(self, text):
        """
        Che thông tin nhạy cảm (PII) trong văn bản.
        
        Args:
            text: Văn bản chứa PII
            
        Returns:
            str: Văn bản đã che PII
        """
        import re
        
        # Patterns for common PII
        patterns = [
            # Phone numbers (Vietnam)
            (r'\b(0[0-9]{9,10})\b', '[SĐT]'),
            (r'\b(\+84[0-9]{9,10})\b', '[SĐT]'),
            # Email
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]'),
            # CMND/CCCD (12 digits)
            (r'\b[0-9]{12}\b', '[CCCD]'),
            # CMND (9 digits)
            (r'\b[0-9]{9}\b', '[CMND]'),
            # Bank account (Vietnamese banks)
            (r'\b[0-9]{10,16}\b', '[TK]'),
            # Credit card
            (r'\b[0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4}\b', '[THẺ]'),
        ]
        
        masked_text = text
        for pattern, replacement in patterns:
            masked_text = re.sub(pattern, replacement, masked_text)
        
        return masked_text
    
    def is_available(self):
        """Check if AI service is available and configured."""
        if not OPENAI_AVAILABLE:
            return False
        try:
            api_key = self.env['ir.config_parameter'].sudo().get_param('ai_integration.openai_api_key', '')
            return bool(api_key and api_key.strip())
        except:
            return False
