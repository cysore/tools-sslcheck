"""
错误处理服务
"""
import socket
import ssl
import time
from typing import Callable, Any, Optional, Dict, List
from datetime import datetime, timezone
import logging


class NetworkErrorHandler:
    """网络错误处理器"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        """
        初始化网络错误处理器
        
        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟时间（秒）
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.logger = logging.getLogger(__name__)
        
        # 可重试的网络错误类型
        self.retryable_errors = {
            socket.timeout,
            socket.gaierror,  # DNS解析错误
            ConnectionRefusedError,
            ConnectionResetError,
            OSError,
            ssl.SSLError
        }
        
        # 不可重试的错误类型
        self.non_retryable_errors = {
            ssl.CertificateError,
            ValueError,
            TypeError
        }
    
    def with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        带重试机制执行函数
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            Any: 函数执行结果
            
        Raises:
            Exception: 重试次数用尽后的最后一个异常
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                # 检查是否是可重试的错误
                if not self._is_retryable_error(e):
                    self.logger.error(f"不可重试的错误: {type(e).__name__}: {str(e)}")
                    raise e
                
                # 如果是最后一次尝试，抛出异常
                if attempt == self.max_retries:
                    self.logger.error(f"重试次数用尽，最终失败: {type(e).__name__}: {str(e)}")
                    raise e
                
                # 计算延迟时间（指数退避）
                delay = self.base_delay * (2 ** attempt)
                
                self.logger.warning(
                    f"尝试 {attempt + 1}/{self.max_retries + 1} 失败: {type(e).__name__}: {str(e)}，"
                    f"{delay:.1f}秒后重试"
                )
                
                time.sleep(delay)
        
        # 理论上不会到达这里，但为了安全起见
        if last_exception:
            raise last_exception
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """
        判断错误是否可重试
        
        Args:
            error: 异常对象
            
        Returns:
            bool: 是否可重试
        """
        error_type = type(error)
        
        # 检查是否是明确不可重试的错误
        if any(issubclass(error_type, non_retryable) for non_retryable in self.non_retryable_errors):
            return False
        
        # 检查是否是可重试的错误
        if any(issubclass(error_type, retryable) for retryable in self.retryable_errors):
            return True
        
        # 检查特定的错误消息
        error_message = str(error).lower()
        retryable_messages = [
            'timeout',
            'connection refused',
            'connection reset',
            'network is unreachable',
            'no route to host',
            'temporary failure',
            'name resolution failed'
        ]
        
        return any(msg in error_message for msg in retryable_messages)
    
    def handle_ssl_connection_error(self, domain: str, error: Exception) -> Dict[str, Any]:
        """
        处理SSL连接错误
        
        Args:
            domain: 域名
            error: 异常对象
            
        Returns:
            Dict[str, Any]: 错误处理结果
        """
        error_info = {
            'domain': domain,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'is_retryable': self._is_retryable_error(error),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'suggested_action': self._get_suggested_action(error)
        }
        
        # 记录错误
        if error_info['is_retryable']:
            self.logger.warning(f"域名 {domain} SSL连接错误（可重试）: {error_info['error_message']}")
        else:
            self.logger.error(f"域名 {domain} SSL连接错误（不可重试）: {error_info['error_message']}")
        
        return error_info
    
    def _get_suggested_action(self, error: Exception) -> str:
        """
        获取错误的建议处理方案
        
        Args:
            error: 异常对象
            
        Returns:
            str: 建议的处理方案
        """
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        if isinstance(error, socket.timeout):
            return "检查网络连接，考虑增加超时时间"
        elif isinstance(error, socket.gaierror):
            return "检查域名是否正确，DNS服务器是否可用"
        elif isinstance(error, ConnectionRefusedError):
            return "检查目标服务器是否运行，端口是否正确"
        elif isinstance(error, ssl.CertificateError):
            return "证书验证失败，检查证书是否有效"
        elif isinstance(error, ssl.SSLError):
            if 'certificate verify failed' in error_message:
                return "证书验证失败，可能是自签名证书或证书链问题"
            elif 'handshake failure' in error_message:
                return "SSL握手失败，检查SSL/TLS版本兼容性"
            else:
                return "SSL连接问题，检查服务器SSL配置"
        elif 'network is unreachable' in error_message:
            return "网络不可达，检查网络连接和路由"
        elif 'no route to host' in error_message:
            return "无法路由到主机，检查防火墙和网络配置"
        else:
            return "检查网络连接和服务器状态"
    
    def get_error_statistics(self, error_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        获取错误统计信息
        
        Args:
            error_list: 错误信息列表
            
        Returns:
            Dict[str, Any]: 错误统计
        """
        if not error_list:
            return {
                'total_errors': 0,
                'retryable_errors': 0,
                'non_retryable_errors': 0,
                'error_types': {},
                'most_common_error': None
            }
        
        error_types = {}
        retryable_count = 0
        
        for error_info in error_list:
            error_type = error_info.get('error_type', 'Unknown')
            error_types[error_type] = error_types.get(error_type, 0) + 1
            
            if error_info.get('is_retryable', False):
                retryable_count += 1
        
        # 找出最常见的错误类型
        most_common_error = max(error_types.items(), key=lambda x: x[1]) if error_types else None
        
        return {
            'total_errors': len(error_list),
            'retryable_errors': retryable_count,
            'non_retryable_errors': len(error_list) - retryable_count,
            'error_types': error_types,
            'most_common_error': most_common_error[0] if most_common_error else None,
            'most_common_error_count': most_common_error[1] if most_common_error else 0
        }


class DNSErrorHandler:
    """DNS错误处理器"""
    
    def __init__(self):
        """初始化DNS错误处理器"""
        self.logger = logging.getLogger(__name__)
    
    def handle_dns_resolution_failure(self, domain: str, error: Exception) -> Dict[str, Any]:
        """
        处理DNS解析失败
        
        Args:
            domain: 域名
            error: DNS错误
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        error_info = {
            'domain': domain,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'dns_check_result': self._check_dns_resolution(domain)
        }
        
        self.logger.error(f"域名 {domain} DNS解析失败: {error_info['error_message']}")
        
        return error_info
    
    def _check_dns_resolution(self, domain: str) -> Dict[str, Any]:
        """
        检查DNS解析状态
        
        Args:
            domain: 域名
            
        Returns:
            Dict[str, Any]: DNS检查结果
        """
        try:
            import socket
            
            # 尝试解析域名
            ip_addresses = socket.gethostbyname_ex(domain)
            
            return {
                'resolvable': True,
                'ip_addresses': ip_addresses[2],
                'canonical_name': ip_addresses[0]
            }
            
        except Exception as e:
            return {
                'resolvable': False,
                'error': str(e)
            }


class TimeoutHandler:
    """超时处理器"""
    
    def __init__(self, default_timeout: int = 10):
        """
        初始化超时处理器
        
        Args:
            default_timeout: 默认超时时间（秒）
        """
        self.default_timeout = default_timeout
        self.logger = logging.getLogger(__name__)
    
    def with_timeout(self, func: Callable, timeout: Optional[int] = None, *args, **kwargs) -> Any:
        """
        带超时控制执行函数
        
        Args:
            func: 要执行的函数
            timeout: 超时时间，如果为None则使用默认值
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            Any: 函数执行结果
            
        Raises:
            TimeoutError: 执行超时
        """
        import signal
        
        timeout = timeout or self.default_timeout
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"函数执行超时（{timeout}秒）")
        
        # 设置超时信号
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
        
        try:
            result = func(*args, **kwargs)
            signal.alarm(0)  # 取消超时
            return result
            
        except TimeoutError:
            self.logger.error(f"函数执行超时: {func.__name__}")
            raise
            
        finally:
            signal.signal(signal.SIGALRM, old_handler)
    
    def handle_timeout_error(self, operation: str, timeout: int) -> Dict[str, Any]:
        """
        处理超时错误
        
        Args:
            operation: 操作名称
            timeout: 超时时间
            
        Returns:
            Dict[str, Any]: 超时处理结果
        """
        error_info = {
            'operation': operation,
            'timeout_seconds': timeout,
            'error_type': 'TimeoutError',
            'error_message': f'{operation} 操作超时（{timeout}秒）',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'suggested_action': '考虑增加超时时间或检查网络连接'
        }
        
        self.logger.error(f"{operation} 操作超时: {timeout}秒")
        
        return error_info