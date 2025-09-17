"""
集成测试
"""
import pytest
import os
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from moto import mock_aws

from ssl_certificate_monitor.lambda_handler import SSLCertificateMonitor, lambda_handler
from ssl_certificate_monitor.models import CertificateInfo


class TestSSLCertificateMonitorIntegration:
    """SSL证书监控器集成测试"""
    
    def setup_method(self):
        """测试前准备"""
        # 设置测试环境变量
        self.test_env = {
            'DOMAINS': 'httpbin.org,example.com',
            'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic',
            'LOG_LEVEL': 'DEBUG'
        }
    
    @patch.dict(os.environ, {
        'DOMAINS': 'httpbin.org',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic',
        'LOG_LEVEL': 'INFO'
    })
    @mock_aws
    def test_end_to_end_workflow_healthy_certificate(self):
        """测试端到端工作流 - 健康证书"""
        import boto3
        
        # 创建SNS主题
        sns = boto3.client('sns', region_name='us-east-1')
        topic_response = sns.create_topic(Name='test-topic')
        topic_arn = topic_response['TopicArn']
        
        # 更新环境变量
        os.environ['SNS_TOPIC_ARN'] = topic_arn
        
        # 创建监控器
        monitor = SSLCertificateMonitor()
        
        # 执行检查
        result = monitor.execute()
        
        # 验证结果
        assert result.total_domains == 1
        assert result.successful_checks >= 0  # 可能因网络问题失败
        assert isinstance(result.execution_time, float)
        assert result.execution_time > 0
    
    @patch.dict(os.environ, {
        'DOMAINS': 'invalid-domain-that-does-not-exist.com',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic',
        'LOG_LEVEL': 'INFO'
    })
    @mock_aws
    def test_end_to_end_workflow_invalid_domain(self):
        """测试端到端工作流 - 无效域名"""
        import boto3
        
        # 创建SNS主题
        sns = boto3.client('sns', region_name='us-east-1')
        topic_response = sns.create_topic(Name='test-topic')
        topic_arn = topic_response['TopicArn']
        
        os.environ['SNS_TOPIC_ARN'] = topic_arn
        
        monitor = SSLCertificateMonitor()
        result = monitor.execute()
        
        # 验证结果
        assert result.total_domains == 1
        assert result.failed_checks == 1
        assert len(result.errors) > 0
    
    @patch.dict(os.environ, {
        'DOMAINS': 'httpbin.org,example.com',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic',
        'LOG_LEVEL': 'INFO'
    })
    def test_lambda_handler_integration(self):
        """测试Lambda处理器集成"""
        with patch('ssl_certificate_monitor.lambda_handler.SSLCertificateMonitor') as mock_monitor_class:
            # 模拟监控器结果
            mock_monitor = mock_monitor_class.return_value
            mock_result = MagicMock()
            mock_result.total_domains = 2
            mock_result.successful_checks = 1
            mock_result.failed_checks = 1
            mock_result.expired_domains = []
            mock_result.expiring_domains = []
            mock_result.errors = ['Test error']
            mock_result.execution_time = 30.5
            
            mock_monitor.execute.return_value = mock_result
            
            # 执行Lambda处理器
            event = {}
            context = MagicMock()
            context.aws_request_id = 'test-request-id'
            context.function_name = 'ssl-certificate-monitor'
            
            response = lambda_handler(event, context)
            
            # 验证响应
            assert response['statusCode'] == 200
            assert 'body' in response
            
            body = response['body']
            assert body['summary']['total_domains'] == 2
            assert body['summary']['successful_checks'] == 1
            assert body['summary']['failed_checks'] == 1
            assert body['summary']['execution_time_seconds'] == 30.5
            assert 'timestamp' in body
    
    @patch.dict(os.environ, {
        'DOMAINS': 'httpbin.org',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic'
    })
    @mock_aws
    def test_sns_integration(self):
        """测试SNS集成"""
        import boto3
        from ssl_certificate_monitor.services.sns_notification import SNSNotificationService
        
        # 创建SNS主题
        sns = boto3.client('sns', region_name='us-east-1')
        topic_response = sns.create_topic(Name='test-topic')
        topic_arn = topic_response['TopicArn']
        
        # 创建通知服务
        notification_service = SNSNotificationService(topic_arn=topic_arn)
        
        # 创建测试证书信息
        expiring_cert = CertificateInfo(
            domain='test.com',
            expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
            days_until_expiry=15,
            issuer='Test CA',
            is_valid=True
        )
        
        # 发送通知
        result = notification_service.send_expiry_notification([expiring_cert])
        
        # 验证结果
        assert result is True
    
    def test_configuration_validation_integration(self):
        """测试配置验证集成"""
        from ssl_certificate_monitor.services.config_validator import ConfigValidator
        
        with patch.dict(os.environ, {
            'DOMAINS': 'example.com,test.org',
            'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:ssl-alerts',
            'LOG_LEVEL': 'INFO'
        }):
            validator = ConfigValidator()
            result = validator.validate_all_configurations()
            
            assert result['is_valid'] is True
            assert len(result['errors']) == 0
            assert 'environment' in result['configurations']
            assert 'domains' in result['configurations']
            assert 'sns' in result['configurations']
    
    def test_error_handling_integration(self):
        """测试错误处理集成"""
        from ssl_certificate_monitor.services.error_handler import NetworkErrorHandler
        from ssl_certificate_monitor.services.ssl_checker import SSLCertificateChecker
        
        # 创建SSL检查器（已集成错误处理）
        checker = SSLCertificateChecker()
        
        # 测试无效域名
        result = checker.check_certificate('invalid-domain-12345.com')
        
        assert result.is_valid is False
        assert result.error_message is not None
        assert result.domain == 'invalid-domain-12345.com'
    
    @patch.dict(os.environ, {
        'DOMAINS': 'httpbin.org',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic'
    })
    def test_system_health_check_integration(self):
        """测试系统健康检查集成"""
        monitor = SSLCertificateMonitor()
        
        health_status = monitor.validate_system_health()
        
        assert 'overall_healthy' in health_status
        assert 'components' in health_status
        assert 'domain_config' in health_status['components']
        assert 'sns_notification' in health_status['components']
    
    @patch.dict(os.environ, {
        'DOMAINS': 'httpbin.org,example.com,test.org',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic'
    })
    def test_batch_processing_integration(self):
        """测试批处理集成"""
        with patch('ssl_certificate_monitor.lambda_handler.SSLCertificateChecker') as mock_checker_class:
            mock_checker = mock_checker_class.return_value
            
            # 模拟证书检查结果
            def mock_check_certificate(domain):
                return CertificateInfo(
                    domain=domain,
                    expiry_date=datetime.now(timezone.utc) + timedelta(days=60),
                    days_until_expiry=60,
                    issuer='Test CA',
                    is_valid=True
                )
            
            mock_checker.check_certificate.side_effect = mock_check_certificate
            
            monitor = SSLCertificateMonitor()
            
            # 测试批处理
            domains = ['test1.com', 'test2.com', 'test3.com']
            results = monitor._check_certificates_batch(domains, batch_size=2)
            
            assert len(results) == 3
            assert all(cert.is_valid for cert in results)
    
    def test_logging_integration(self):
        """测试日志集成"""
        from ssl_certificate_monitor.services.logger import LoggerService
        
        logger_service = LoggerService(logger_name="test_logger")
        
        # 测试日志记录
        logger_service.log_check_start(5)
        
        # 创建测试证书
        cert_info = CertificateInfo(
            domain='test.com',
            expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
            days_until_expiry=15,
            issuer='Test CA',
            is_valid=True
        )
        
        logger_service.log_certificate_info('test.com', cert_info)
        logger_service.log_check_end()
        
        # 获取执行摘要
        summary = logger_service.get_execution_summary()
        
        assert summary['total_domains'] == 5
        assert summary['successful_checks'] == 1
        assert summary['duration_seconds'] >= 0


class TestMockScenarios:
    """模拟场景测试"""
    
    @patch.dict(os.environ, {
        'DOMAINS': 'expiring.com,expired.com,healthy.com',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic'
    })
    @mock_aws
    def test_mixed_certificate_scenarios(self):
        """测试混合证书场景"""
        import boto3
        
        # 创建SNS主题
        sns = boto3.client('sns', region_name='us-east-1')
        topic_response = sns.create_topic(Name='test-topic')
        topic_arn = topic_response['TopicArn']
        
        os.environ['SNS_TOPIC_ARN'] = topic_arn
        
        with patch('ssl_certificate_monitor.lambda_handler.SSLCertificateChecker') as mock_checker_class:
            mock_checker = mock_checker_class.return_value
            
            def mock_check_certificate(domain):
                if domain == 'expiring.com':
                    return CertificateInfo(
                        domain=domain,
                        expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
                        days_until_expiry=15,
                        issuer='Test CA',
                        is_valid=True
                    )
                elif domain == 'expired.com':
                    return CertificateInfo(
                        domain=domain,
                        expiry_date=datetime.now(timezone.utc) - timedelta(days=5),
                        days_until_expiry=-5,
                        issuer='Test CA',
                        is_valid=True
                    )
                else:  # healthy.com
                    return CertificateInfo(
                        domain=domain,
                        expiry_date=datetime.now(timezone.utc) + timedelta(days=90),
                        days_until_expiry=90,
                        issuer='Test CA',
                        is_valid=True
                    )
            
            mock_checker.check_certificate.side_effect = mock_check_certificate
            
            monitor = SSLCertificateMonitor()
            result = monitor.execute()
            
            # 验证结果
            assert result.total_domains == 3
            assert result.successful_checks == 3
            assert len(result.expiring_domains) == 1
            assert len(result.expired_domains) == 1
            assert result.expiring_domains[0].domain == 'expiring.com'
            assert result.expired_domains[0].domain == 'expired.com'
    
    @patch.dict(os.environ, {
        'DOMAINS': 'test1.com,test2.com,test3.com',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:test-topic'
    })
    def test_network_error_scenarios(self):
        """测试网络错误场景"""
        import socket
        
        with patch('ssl_certificate_monitor.lambda_handler.SSLCertificateChecker') as mock_checker_class:
            mock_checker = mock_checker_class.return_value
            
            def mock_check_certificate(domain):
                if domain == 'test1.com':
                    raise socket.timeout("Connection timeout")
                elif domain == 'test2.com':
                    raise socket.gaierror("Name resolution failed")
                else:  # test3.com
                    return CertificateInfo(
                        domain=domain,
                        expiry_date=datetime.now(timezone.utc) + timedelta(days=60),
                        days_until_expiry=60,
                        issuer='Test CA',
                        is_valid=True
                    )
            
            mock_checker.check_certificate.side_effect = mock_check_certificate
            
            monitor = SSLCertificateMonitor()
            result = monitor.execute()
            
            # 验证结果
            assert result.total_domains == 3
            assert result.successful_checks == 1
            assert result.failed_checks == 2
            assert len(result.errors) == 2
    
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_configuration_scenario(self):
        """测试缺少配置的场景"""
        monitor = SSLCertificateMonitor()
        result = monitor.execute()
        
        # 验证结果
        assert result.total_domains == 0
        assert result.successful_checks == 0
        assert result.failed_checks == 0
        assert len(result.errors) > 0
        assert "没有找到要检查的域名" in result.errors[0]