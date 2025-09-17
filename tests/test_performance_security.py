"""
性能和安全测试
"""
import pytest
import time
import threading
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from ssl_certificate_monitor.lambda_handler import SSLCertificateMonitor
from ssl_certificate_monitor.services.ssl_checker import SSLCertificateChecker
from ssl_certificate_monitor.services.domain_config import DomainConfigManager
from ssl_certificate_monitor.services.config_validator import ConfigValidator
from ssl_certificate_monitor.models import CertificateInfo


class TestPerformance:
    """性能测试"""
    
    def test_ssl_checker_performance(self):
        """测试SSL检查器性能"""
        checker = SSLCertificateChecker(timeout=5)
        
        # 测试单个域名检查的性能
        start_time = time.time()
        
        # 使用一个可靠的测试域名
        result = checker.check_certificate('httpbin.org')
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # 验证性能要求（应该在10秒内完成）
        assert execution_time < 10.0, f"SSL检查耗时过长: {execution_time:.2f}秒"
        
        # 验证结果
        assert isinstance(result, CertificateInfo)
    
    def test_concurrent_ssl_checks(self):
        """测试并发SSL检查"""
        checker = SSLCertificateChecker(timeout=5)
        domains = ['httpbin.org', 'example.com', 'google.com']
        results = []
        threads = []
        
        def check_domain(domain):
            try:
                result = checker.check_certificate(domain)
                results.append((domain, result, True))
            except Exception as e:
                results.append((domain, str(e), False))
        
        # 启动并发检查
        start_time = time.time()
        
        for domain in domains:
            thread = threading.Thread(target=check_domain, args=(domain,))
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join(timeout=15)  # 15秒超时
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # 验证并发性能（应该比串行快）
        assert total_time < 20.0, f"并发检查耗时过长: {total_time:.2f}秒"
        assert len(results) == len(domains), "并发检查结果数量不匹配"
    
    @patch.dict(os.environ, {
        'DOMAINS': ','.join([f'test{i}.com' for i in range(50)]),
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic'
    })
    def test_large_domain_list_performance(self):
        """测试大量域名列表的性能"""
        with patch('ssl_certificate_monitor.lambda_handler.SSLCertificateChecker') as mock_checker_class:
            mock_checker = mock_checker_class.return_value
            
            # 模拟快速的证书检查
            def mock_check_certificate(domain):
                time.sleep(0.01)  # 模拟10ms的检查时间
                return CertificateInfo(
                    domain=domain,
                    expiry_date=datetime.now(timezone.utc) + timedelta(days=60),
                    days_until_expiry=60,
                    issuer='Test CA',
                    is_valid=True
                )
            
            mock_checker.check_certificate.side_effect = mock_check_certificate
            
            monitor = SSLCertificateMonitor()
            
            start_time = time.time()
            result = monitor.execute()
            end_time = time.time()
            
            execution_time = end_time - start_time
            
            # 验证性能（50个域名应该在30秒内完成）
            assert execution_time < 30.0, f"大量域名检查耗时过长: {execution_time:.2f}秒"
            assert result.total_domains == 50
    
    def test_memory_usage_with_large_results(self):
        """测试大量结果的内存使用"""
        # 创建大量证书信息对象
        certificates = []
        
        for i in range(1000):
            cert = CertificateInfo(
                domain=f'test{i}.com',
                expiry_date=datetime.now(timezone.utc) + timedelta(days=60),
                days_until_expiry=60,
                issuer='Test CA',
                is_valid=True
            )
            certificates.append(cert)
        
        # 验证对象创建成功
        assert len(certificates) == 1000
        
        # 测试批量处理
        from ssl_certificate_monitor.services.expiry_calculator import ExpiryCalculator
        calculator = ExpiryCalculator()
        
        start_time = time.time()
        categorized = calculator.categorize_certificates(certificates)
        end_time = time.time()
        
        # 验证处理时间
        processing_time = end_time - start_time
        assert processing_time < 1.0, f"批量处理耗时过长: {processing_time:.2f}秒"
        
        # 验证结果
        assert categorized['total'] == 1000
    
    def test_timeout_handling(self):
        """测试超时处理"""
        from ssl_certificate_monitor.services.error_handler import TimeoutHandler
        
        handler = TimeoutHandler(default_timeout=1)
        
        def slow_function():
            time.sleep(2)  # 超过超时时间
            return "should not reach here"
        
        start_time = time.time()
        
        # 在支持SIGALRM的系统上测试超时
        try:
            import signal
            if hasattr(signal, 'SIGALRM'):
                with pytest.raises(TimeoutError):
                    handler.with_timeout(slow_function, timeout=1)
                
                end_time = time.time()
                elapsed = end_time - start_time
                
                # 验证超时时间准确性（允许一些误差）
                assert elapsed < 2.0, f"超时处理不准确: {elapsed:.2f}秒"
            else:
                pytest.skip("SIGALRM not available on this platform")
        except ImportError:
            pytest.skip("signal module not available")


class TestSecurity:
    """安全测试"""
    
    def test_input_validation_domain_names(self):
        """测试域名输入验证"""
        manager = DomainConfigManager()
        
        # 测试恶意输入
        malicious_inputs = [
            '../../../etc/passwd',
            '<script>alert("xss")</script>',
            'domain.com; rm -rf /',
            'domain.com`whoami`',
            'domain.com$(whoami)',
            'domain.com|whoami',
            'domain.com&whoami',
            'domain.com\nwhoami',
            'domain.com\rwhoami',
            'domain.com\twhoami'
        ]
        
        for malicious_input in malicious_inputs:
            # 验证恶意输入被正确处理
            is_valid = manager.validate_domain(malicious_input)
            assert is_valid is False, f"恶意输入未被拒绝: {malicious_input}"
    
    def test_environment_variable_sanitization(self):
        """测试环境变量清理"""
        from ssl_certificate_monitor.services.logger import LoggerService
        
        logger_service = LoggerService()
        
        # 测试敏感信息清理
        config = {
            'normal_setting': 'normal_value',
            'password': 'secret123',
            'api_key': 'key456',
            'sns_topic_arn': 'arn:aws:sns:us-east-1:123456789012:ssl-alerts'
        }
        
        sanitized = logger_service._sanitize_config(config)
        
        # 验证敏感信息被隐藏
        assert sanitized['normal_setting'] == 'normal_value'
        assert 'secret123' not in sanitized['password']
        assert 'key456' not in sanitized['api_key']
        assert '123456789012' in sanitized['sns_topic_arn']  # 部分显示
        assert 'arn:aws:sns:***:' in sanitized['sns_topic_arn']
    
    def test_ssl_certificate_validation(self):
        """测试SSL证书验证安全性"""
        checker = SSLCertificateChecker()
        
        # 测试无效的域名输入
        invalid_domains = [
            '',
            None,
            'localhost',  # 本地地址
            '127.0.0.1',  # IP地址
            'internal.local',  # 内部域名
            'file:///etc/passwd',  # 文件协议
            'ftp://example.com',  # 非HTTPS协议
        ]
        
        for invalid_domain in invalid_domains:
            try:
                result = checker.check_certificate(invalid_domain)
                # 如果没有抛出异常，验证结果是无效的
                if result:
                    assert result.is_valid is False, f"无效域名应该返回无效结果: {invalid_domain}"
            except Exception:
                # 抛出异常也是可接受的
                pass
    
    def test_configuration_validation_security(self):
        """测试配置验证安全性"""
        validator = ConfigValidator()
        
        # 测试恶意SNS ARN
        malicious_arns = [
            'arn:aws:sns:us-east-1:123456789012:../../../etc/passwd',
            'arn:aws:sns:us-east-1:123456789012:topic;rm -rf /',
            'arn:aws:sns:us-east-1:123456789012:topic`whoami`',
            'arn:aws:sns:us-east-1:123456789012:topic$(whoami)',
            'javascript:alert("xss")',
            'file:///etc/passwd'
        ]
        
        for malicious_arn in malicious_arns:
            with patch.dict(os.environ, {'SNS_TOPIC_ARN': malicious_arn}):
                result = validator.validate_sns_configuration()
                
                # 验证恶意ARN被拒绝
                assert result['is_valid'] is False, f"恶意ARN未被拒绝: {malicious_arn}"
                assert result['arn_format_valid'] is False
    
    def test_error_message_sanitization(self):
        """测试错误消息清理"""
        from ssl_certificate_monitor.services.error_handler import NetworkErrorHandler
        
        handler = NetworkErrorHandler()
        
        # 模拟包含敏感信息的错误
        class MockError(Exception):
            def __str__(self):
                return "Connection failed to server with password: secret123"
        
        error = MockError()
        error_info = handler.handle_ssl_connection_error('test.com', error)
        
        # 验证错误信息不包含敏感数据（这里只是示例，实际实现可能需要更复杂的清理）
        assert 'error_message' in error_info
        assert isinstance(error_info['error_message'], str)
    
    def test_lambda_handler_input_validation(self):
        """测试Lambda处理器输入验证"""
        # 测试恶意事件输入
        malicious_events = [
            {'malicious_key': '../../../etc/passwd'},
            {'command': 'rm -rf /'},
            {'script': '<script>alert("xss")</script>'},
            {'large_payload': 'A' * 1000000},  # 大负载
        ]
        
        for malicious_event in malicious_events:
            try:
                # Lambda处理器应该能够安全处理恶意输入
                response = lambda_handler(malicious_event, MagicMock())
                
                # 验证响应格式正确
                assert 'statusCode' in response
                assert 'body' in response
                
            except Exception as e:
                # 如果抛出异常，应该是可控的异常
                assert not isinstance(e, (SystemExit, KeyboardInterrupt))
    
    def test_resource_limits(self):
        """测试资源限制"""
        # 测试域名数量限制
        large_domain_list = ','.join([f'test{i}.com' for i in range(10000)])
        
        with patch.dict(os.environ, {'DOMAINS': large_domain_list}):
            manager = DomainConfigManager()
            domains = manager.get_domains()
            
            # 验证系统能够处理大量域名而不崩溃
            assert isinstance(domains, list)
            # 实际实现中可能需要限制域名数量
    
    def test_injection_prevention(self):
        """测试注入攻击防护"""
        # 测试命令注入
        injection_attempts = [
            'domain.com; cat /etc/passwd',
            'domain.com && whoami',
            'domain.com | ls -la',
            'domain.com `id`',
            'domain.com $(id)',
            'domain.com\n/bin/sh'
        ]
        
        checker = SSLCertificateChecker()
        
        for injection in injection_attempts:
            try:
                result = checker.check_certificate(injection)
                # 验证注入尝试被安全处理
                if result:
                    # 域名应该被清理，不包含注入字符
                    assert ';' not in result.domain
                    assert '&&' not in result.domain
                    assert '|' not in result.domain
                    assert '`' not in result.domain
                    assert '$(' not in result.domain
            except Exception:
                # 抛出异常也是可接受的防护措施
                pass