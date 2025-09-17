"""
错误处理服务测试
"""
import pytest
import socket
import ssl
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from ssl_certificate_monitor.services.error_handler import (
    NetworkErrorHandler, 
    DNSErrorHandler, 
    TimeoutHandler
)


class TestNetworkErrorHandler:
    """网络错误处理器测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.handler = NetworkErrorHandler(max_retries=2, base_delay=0.1)
    
    def test_init(self):
        """测试初始化"""
        assert self.handler.max_retries == 2
        assert self.handler.base_delay == 0.1
        assert socket.timeout in self.handler.retryable_errors
        assert ssl.CertificateError in self.handler.non_retryable_errors
    
    def test_is_retryable_error_retryable(self):
        """测试可重试错误判断"""
        retryable_errors = [
            socket.timeout("Connection timeout"),
            socket.gaierror("Name resolution failed"),
            ConnectionRefusedError("Connection refused"),
            OSError("Network error")
        ]
        
        for error in retryable_errors:
            assert self.handler._is_retryable_error(error) is True
    
    def test_is_retryable_error_non_retryable(self):
        """测试不可重试错误判断"""
        non_retryable_errors = [
            ssl.CertificateError("Certificate error"),
            ValueError("Invalid value"),
            TypeError("Type error")
        ]
        
        for error in non_retryable_errors:
            assert self.handler._is_retryable_error(error) is False
    
    def test_is_retryable_error_by_message(self):
        """测试通过错误消息判断可重试性"""
        # 可重试的错误消息
        retryable_error = Exception("Connection timeout occurred")
        assert self.handler._is_retryable_error(retryable_error) is True
        
        # 不可重试的错误消息
        non_retryable_error = Exception("Invalid configuration")
        assert self.handler._is_retryable_error(non_retryable_error) is False
    
    @patch('time.sleep')
    def test_with_retry_success_first_attempt(self, mock_sleep):
        """测试第一次尝试就成功"""
        def test_func():
            return "success"
        
        result = self.handler.with_retry(test_func)
        
        assert result == "success"
        mock_sleep.assert_not_called()
    
    @patch('time.sleep')
    def test_with_retry_success_after_retry(self, mock_sleep):
        """测试重试后成功"""
        call_count = 0
        
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise socket.timeout("Connection timeout")
            return "success"
        
        result = self.handler.with_retry(test_func)
        
        assert result == "success"
        assert call_count == 2
        mock_sleep.assert_called_once_with(0.1)  # base_delay * 2^0
    
    @patch('time.sleep')
    def test_with_retry_max_retries_exceeded(self, mock_sleep):
        """测试超过最大重试次数"""
        def test_func():
            raise socket.timeout("Connection timeout")
        
        with pytest.raises(socket.timeout):
            self.handler.with_retry(test_func)
        
        # 验证重试次数和延迟
        assert mock_sleep.call_count == 2  # max_retries = 2
        mock_sleep.assert_any_call(0.1)  # 第一次重试延迟
        mock_sleep.assert_any_call(0.2)  # 第二次重试延迟
    
    def test_with_retry_non_retryable_error(self):
        """测试不可重试错误"""
        def test_func():
            raise ValueError("Invalid value")
        
        with pytest.raises(ValueError):
            self.handler.with_retry(test_func)
    
    def test_handle_ssl_connection_error_retryable(self):
        """测试处理可重试的SSL连接错误"""
        error = socket.timeout("Connection timeout")
        
        result = self.handler.handle_ssl_connection_error("example.com", error)
        
        assert result['domain'] == "example.com"
        assert result['error_type'] == "TimeoutError"
        assert result['is_retryable'] is True
        assert "检查网络连接" in result['suggested_action']
        assert 'timestamp' in result
    
    def test_handle_ssl_connection_error_non_retryable(self):
        """测试处理不可重试的SSL连接错误"""
        error = ssl.CertificateError("Certificate verification failed")
        
        result = self.handler.handle_ssl_connection_error("example.com", error)
        
        assert result['domain'] == "example.com"
        assert result['error_type'] == "SSLCertVerificationError"
        assert result['is_retryable'] is False
        assert "证书验证失败" in result['suggested_action']
    
    def test_get_suggested_action(self):
        """测试获取建议处理方案"""
        test_cases = [
            (socket.timeout("timeout"), "检查网络连接"),
            (socket.gaierror("DNS error"), "检查域名是否正确"),
            (ConnectionRefusedError("refused"), "检查目标服务器是否运行"),
            (ssl.CertificateError("cert error"), "证书验证失败"),
            (Exception("network is unreachable"), "网络不可达")
        ]
        
        for error, expected_keyword in test_cases:
            suggestion = self.handler._get_suggested_action(error)
            assert expected_keyword in suggestion
    
    def test_get_error_statistics_empty(self):
        """测试空错误列表的统计"""
        stats = self.handler.get_error_statistics([])
        
        assert stats['total_errors'] == 0
        assert stats['retryable_errors'] == 0
        assert stats['non_retryable_errors'] == 0
        assert stats['error_types'] == {}
        assert stats['most_common_error'] is None
    
    def test_get_error_statistics_with_errors(self):
        """测试有错误的统计"""
        error_list = [
            {'error_type': 'timeout', 'is_retryable': True},
            {'error_type': 'timeout', 'is_retryable': True},
            {'error_type': 'CertificateError', 'is_retryable': False},
            {'error_type': 'gaierror', 'is_retryable': True}
        ]
        
        stats = self.handler.get_error_statistics(error_list)
        
        assert stats['total_errors'] == 4
        assert stats['retryable_errors'] == 3
        assert stats['non_retryable_errors'] == 1
        assert stats['error_types']['timeout'] == 2
        assert stats['most_common_error'] == 'timeout'
        assert stats['most_common_error_count'] == 2


class TestDNSErrorHandler:
    """DNS错误处理器测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.handler = DNSErrorHandler()
    
    def test_handle_dns_resolution_failure(self):
        """测试处理DNS解析失败"""
        error = socket.gaierror("Name resolution failed")
        
        with patch.object(self.handler, '_check_dns_resolution') as mock_check:
            mock_check.return_value = {'resolvable': False, 'error': 'DNS error'}
            
            result = self.handler.handle_dns_resolution_failure("invalid.com", error)
            
            assert result['domain'] == "invalid.com"
            assert result['error_type'] == "gaierror"
            assert result['dns_check_result']['resolvable'] is False
            assert 'timestamp' in result
    
    @patch('socket.gethostbyname_ex')
    def test_check_dns_resolution_success(self, mock_gethostbyname):
        """测试DNS解析成功"""
        mock_gethostbyname.return_value = ('example.com', [], ['192.168.1.1'])
        
        result = self.handler._check_dns_resolution("example.com")
        
        assert result['resolvable'] is True
        assert result['ip_addresses'] == ['192.168.1.1']
        assert result['canonical_name'] == 'example.com'
    
    @patch('socket.gethostbyname_ex')
    def test_check_dns_resolution_failure(self, mock_gethostbyname):
        """测试DNS解析失败"""
        mock_gethostbyname.side_effect = socket.gaierror("Name resolution failed")
        
        result = self.handler._check_dns_resolution("invalid.com")
        
        assert result['resolvable'] is False
        assert 'error' in result


class TestTimeoutHandler:
    """超时处理器测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.handler = TimeoutHandler(default_timeout=5)
    
    def test_init(self):
        """测试初始化"""
        assert self.handler.default_timeout == 5
    
    @pytest.mark.skipif(
        not hasattr(signal := __import__('signal'), 'SIGALRM'),
        reason="SIGALRM not available on this platform"
    )
    def test_with_timeout_success(self):
        """测试超时控制成功执行"""
        def test_func():
            return "success"
        
        result = self.handler.with_timeout(test_func, timeout=1)
        
        assert result == "success"
    
    @pytest.mark.skipif(
        not hasattr(signal := __import__('signal'), 'SIGALRM'),
        reason="SIGALRM not available on this platform"
    )
    def test_with_timeout_timeout_error(self):
        """测试超时错误"""
        def slow_func():
            time.sleep(2)
            return "should not reach here"
        
        with pytest.raises(TimeoutError):
            self.handler.with_timeout(slow_func, timeout=1)
    
    def test_handle_timeout_error(self):
        """测试处理超时错误"""
        result = self.handler.handle_timeout_error("SSL connection", 10)
        
        assert result['operation'] == "SSL connection"
        assert result['timeout_seconds'] == 10
        assert result['error_type'] == 'TimeoutError'
        assert "SSL connection 操作超时" in result['error_message']
        assert "考虑增加超时时间" in result['suggested_action']
        assert 'timestamp' in result
    
    def test_with_timeout_default_timeout(self):
        """测试使用默认超时时间"""
        def test_func():
            return "success"
        
        # 不指定timeout参数，应该使用默认值
        result = self.handler.with_timeout(test_func)
        
        assert result == "success"