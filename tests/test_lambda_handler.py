"""
Lambda处理器测试
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from ssl_certificate_monitor.lambda_handler import SSLCertificateMonitor, lambda_handler
from ssl_certificate_monitor.models import CertificateInfo


class TestSSLCertificateMonitor:
    """SSL证书监控器测试类"""
    
    def setup_method(self):
        """测试前准备"""
        # Mock所有服务组件
        with patch('ssl_certificate_monitor.lambda_handler.LoggerService') as mock_logger, \
             patch('ssl_certificate_monitor.lambda_handler.DomainConfigManager') as mock_domain, \
             patch('ssl_certificate_monitor.lambda_handler.SSLCertificateChecker') as mock_ssl, \
             patch('ssl_certificate_monitor.lambda_handler.SNSNotificationService') as mock_sns, \
             patch('ssl_certificate_monitor.lambda_handler.ExpiryCalculator') as mock_calc:
            
            self.mock_logger = mock_logger.return_value
            self.mock_domain = mock_domain.return_value
            self.mock_ssl = mock_ssl.return_value
            self.mock_sns = mock_sns.return_value
            self.mock_calc = mock_calc.return_value
            
            self.monitor = SSLCertificateMonitor()
    
    def test_init(self):
        """测试监控器初始化"""
        assert self.monitor.logger_service == self.mock_logger
        assert self.monitor.domain_manager == self.mock_domain
        assert self.monitor.ssl_checker == self.mock_ssl
        assert self.monitor.notification_service == self.mock_sns
        assert self.monitor.expiry_calculator == self.mock_calc
        
        # 验证配置信息被记录
        self.mock_logger.log_configuration_info.assert_called_once()
    
    def test_execute_no_domains(self):
        """测试没有域名时的执行"""
        # 设置mock返回值
        self.mock_domain.get_domains.return_value = []
        
        result = self.monitor.execute()
        
        assert result.total_domains == 0
        assert result.successful_checks == 0
        assert result.failed_checks == 0
        assert result.expiring_domains == []
        assert result.expired_domains == []
        assert "没有找到要检查的域名" in result.errors
        
        # 验证日志记录
        self.mock_logger.logger.warning.assert_called_with("没有找到要检查的域名")
    
    def test_execute_successful_checks(self):
        """测试成功的证书检查"""
        # 准备测试数据
        domains = ['example.com', 'test.com']
        certificates = [
            CertificateInfo(
                domain='example.com',
                expiry_date=datetime.now(timezone.utc) + timedelta(days=60),
                days_until_expiry=60,
                issuer='Test CA',
                is_valid=True
            ),
            CertificateInfo(
                domain='test.com',
                expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
                days_until_expiry=15,
                issuer='Test CA',
                is_valid=True
            )
        ]
        
        # 设置mock返回值
        self.mock_domain.get_domains.return_value = domains
        self.mock_ssl.check_certificate.side_effect = certificates
        self.mock_calc.categorize_certificates.return_value = {
            'expired': [],
            'expiring_soon': [certificates[1]],  # test.com即将过期
            'healthy': [certificates[0]]
        }
        self.mock_sns.send_expiry_notification.return_value = True
        
        result = self.monitor.execute()
        
        assert result.total_domains == 2
        assert result.successful_checks == 2
        assert result.failed_checks == 0
        assert len(result.expiring_domains) == 1
        assert result.expiring_domains[0].domain == 'test.com'
        assert len(result.expired_domains) == 0
        
        # 验证服务调用
        self.mock_logger.log_check_start.assert_called_once_with(2)
        assert self.mock_ssl.check_certificate.call_count == 2
        assert self.mock_logger.log_certificate_info.call_count == 2
        self.mock_sns.send_expiry_notification.assert_called_once()
        self.mock_logger.log_notification_sent.assert_called_once_with("SNS", 1, True)
        self.mock_logger.log_check_end.assert_called_once()
        self.mock_logger.log_execution_summary.assert_called_once()
    
    def test_execute_with_errors(self):
        """测试包含错误的证书检查"""
        domains = ['example.com', 'invalid.com']
        
        # 第一个域名成功，第二个域名失败
        def check_certificate_side_effect(domain):
            if domain == 'example.com':
                return CertificateInfo(
                    domain='example.com',
                    expiry_date=datetime.now(timezone.utc) + timedelta(days=60),
                    days_until_expiry=60,
                    issuer='Test CA',
                    is_valid=True
                )
            else:
                raise Exception("Connection failed")
        
        # 设置mock返回值
        self.mock_domain.get_domains.return_value = domains
        self.mock_ssl.check_certificate.side_effect = check_certificate_side_effect
        self.mock_calc.categorize_certificates.return_value = {
            'expired': [],
            'expiring_soon': [],
            'healthy': []
        }
        
        result = self.monitor.execute()
        
        assert result.total_domains == 2
        assert result.successful_checks == 1
        assert result.failed_checks == 1
        assert "Connection failed" in result.errors
        
        # 验证错误日志记录
        self.mock_logger.log_error.assert_called_once()
    
    def test_execute_notification_failure(self):
        """测试通知发送失败"""
        domains = ['expired.com']
        expired_cert = CertificateInfo(
            domain='expired.com',
            expiry_date=datetime.now(timezone.utc) - timedelta(days=5),
            days_until_expiry=-5,
            issuer='Test CA',
            is_valid=True
        )
        
        # 设置mock返回值
        self.mock_domain.get_domains.return_value = domains
        self.mock_ssl.check_certificate.return_value = expired_cert
        self.mock_calc.categorize_certificates.return_value = {
            'expired': [expired_cert],
            'expiring_soon': [],
            'healthy': []
        }
        self.mock_sns.send_expiry_notification.return_value = False
        
        result = self.monitor.execute()
        
        assert result.total_domains == 1
        assert len(result.expired_domains) == 1
        
        # 验证通知失败被记录
        self.mock_logger.log_notification_sent.assert_called_once_with("SNS", 1, False)
    
    def test_execute_critical_error(self):
        """测试严重错误处理"""
        # 设置domain_manager抛出异常
        self.mock_domain.get_domains.side_effect = Exception("Critical error")
        
        result = self.monitor.execute()
        
        assert result.total_domains == 0
        assert result.successful_checks == 0
        assert result.failed_checks == 0
        assert "Critical error" in result.errors
        
        # 验证错误日志记录
        self.mock_logger.logger.error.assert_called()
    
    def test_check_certificates_batch(self):
        """测试批处理证书检查"""
        domains = ['example1.com', 'example2.com', 'example3.com']
        certificates = [
            CertificateInfo(f'example{i}.com', datetime.now(timezone.utc) + timedelta(days=60), 60, 'Test CA', True)
            for i in range(1, 4)
        ]
        
        # 设置mock返回值
        self.mock_ssl.check_certificate.side_effect = certificates
        
        result = self.monitor._check_certificates_batch(domains, batch_size=2)
        
        assert len(result) == 3
        assert all(cert.is_valid for cert in result)
        assert self.mock_ssl.check_certificate.call_count == 3
        assert self.mock_logger.log_certificate_info.call_count == 3
    
    def test_send_notifications_no_issues(self):
        """测试没有问题时的通知发送"""
        categorized = {
            'expired': [],
            'expiring_soon': [],
            'healthy': []
        }
        
        result = self.monitor._send_notifications(categorized)
        
        assert result is True
        self.mock_logger.logger.info.assert_called_with("所有证书状态正常，无需发送通知")
        self.mock_sns.send_expiry_notification.assert_not_called()
    
    def test_send_notifications_small_batch(self):
        """测试小批量通知发送"""
        expiring_cert = CertificateInfo('test.com', datetime.now(timezone.utc) + timedelta(days=15), 15, 'CA', True)
        categorized = {
            'expired': [],
            'expiring_soon': [expiring_cert],
            'healthy': []
        }
        
        self.mock_sns.send_expiry_notification.return_value = True
        
        result = self.monitor._send_notifications(categorized)
        
        assert result is True
        self.mock_sns.send_expiry_notification.assert_called_once_with([expiring_cert])
        self.mock_logger.log_notification_sent.assert_called_once_with("SNS", 1, True)
    
    def test_send_notifications_large_batch(self):
        """测试大批量通知发送"""
        # 创建25个即将过期的证书
        expiring_certs = [
            CertificateInfo(f'test{i}.com', datetime.now(timezone.utc) + timedelta(days=15), 15, 'CA', True)
            for i in range(25)
        ]
        categorized = {
            'expired': [],
            'expiring_soon': expiring_certs,
            'healthy': []
        }
        
        self.mock_sns.send_batch_notifications.return_value = True
        
        result = self.monitor._send_notifications(categorized)
        
        assert result is True
        self.mock_sns.send_batch_notifications.assert_called_once_with(expiring_certs)
        self.mock_logger.log_notification_sent.assert_called_once_with("SNS", 25, True)
    
    def test_send_notifications_with_error(self):
        """测试通知发送错误处理"""
        expiring_cert = CertificateInfo('test.com', datetime.now(timezone.utc) + timedelta(days=15), 15, 'CA', True)
        categorized = {
            'expired': [],
            'expiring_soon': [expiring_cert],
            'healthy': []
        }
        
        # 设置通知发送失败
        self.mock_sns.send_expiry_notification.side_effect = Exception("SNS error")
        self.mock_sns.sns_client.publish.return_value = {'MessageId': 'error-msg-id'}
        
        result = self.monitor._send_notifications(categorized)
        
        assert result is False
        self.mock_logger.logger.error.assert_called()
        # 验证尝试发送错误通知
        self.mock_sns.sns_client.publish.assert_called_once()
    
    def test_validate_system_health_healthy(self):
        """测试系统健康检查 - 健康状态"""
        # 设置mock返回值
        self.mock_domain.validate_configuration.return_value = {
            'total_domains': 3,
            'valid_domains': ['a.com', 'b.com', 'c.com']
        }
        self.mock_sns.get_configuration_status.return_value = {
            'configuration_valid': True,
            'topic_arn': 'arn:aws:sns:us-east-1:123:test'
        }
        self.mock_sns.test_connection.return_value = True
        
        health = self.monitor.validate_system_health()
        
        assert health['overall_healthy'] is True
        assert health['components']['domain_config']['healthy'] is True
        assert health['components']['sns_notification']['healthy'] is True
        assert health['components']['sns_connection']['healthy'] is True
        assert len(health['issues']) == 0
    
    def test_validate_system_health_unhealthy(self):
        """测试系统健康检查 - 不健康状态"""
        # 设置mock返回值
        self.mock_domain.validate_configuration.return_value = {
            'total_domains': 0,
            'valid_domains': []
        }
        self.mock_sns.get_configuration_status.return_value = {
            'configuration_valid': False,
            'topic_arn': None
        }
        
        health = self.monitor.validate_system_health()
        
        assert health['overall_healthy'] is False
        assert health['components']['domain_config']['healthy'] is False
        assert health['components']['sns_notification']['healthy'] is False
        assert "没有配置要监控的域名" in health['issues']
        assert "SNS通知配置无效" in health['issues']


class TestLambdaHandler:
    """Lambda处理器函数测试类"""
    
    @patch('ssl_certificate_monitor.lambda_handler.SSLCertificateMonitor')
    def test_lambda_handler_success(self, mock_monitor_class):
        """测试Lambda处理器成功执行"""
        # 准备测试数据
        mock_monitor = mock_monitor_class.return_value
        mock_result = MagicMock()
        mock_result.total_domains = 3
        mock_result.successful_checks = 2
        mock_result.failed_checks = 1
        mock_result.expired_domains = []
        mock_result.expiring_domains = [MagicMock(domain='test.com')]
        mock_result.errors = ['Some error']
        mock_result.execution_time = 45.5
        
        mock_monitor.execute.return_value = mock_result
        
        # 执行Lambda处理器
        event = {}
        context = MagicMock()
        
        response = lambda_handler(event, context)
        
        # 验证响应
        assert response['statusCode'] == 200
        assert response['body']['message'] == 'SSL Certificate Monitor executed successfully'
        
        summary = response['body']['summary']
        assert summary['total_domains'] == 3
        assert summary['successful_checks'] == 2
        assert summary['failed_checks'] == 1
        assert summary['expired_certificates'] == 0
        assert summary['expiring_certificates'] == 1
        assert summary['execution_time_seconds'] == 45.5
        assert summary['success_rate'] == 2/3
        
        assert response['body']['expiring_domains'] == ['test.com']
        assert response['body']['errors'] == ['Some error']
        assert 'timestamp' in response['body']
    
    @patch('ssl_certificate_monitor.lambda_handler.SSLCertificateMonitor')
    def test_lambda_handler_no_domains_error(self, mock_monitor_class):
        """测试Lambda处理器没有域名的错误情况"""
        mock_monitor = mock_monitor_class.return_value
        mock_result = MagicMock()
        mock_result.total_domains = 0
        mock_result.successful_checks = 0
        mock_result.failed_checks = 0
        mock_result.expired_domains = []
        mock_result.expiring_domains = []
        mock_result.errors = ['No domains found']
        mock_result.execution_time = 1.0
        
        mock_monitor.execute.return_value = mock_result
        
        response = lambda_handler({}, MagicMock())
        
        assert response['statusCode'] == 500
        assert response['body']['message'] == 'SSL Certificate Monitor failed to execute'
    
    @patch('ssl_certificate_monitor.lambda_handler.SSLCertificateMonitor')
    def test_lambda_handler_critical_exception(self, mock_monitor_class):
        """测试Lambda处理器严重异常"""
        # 设置监控器初始化失败
        mock_monitor_class.side_effect = Exception("Critical initialization error")
        
        response = lambda_handler({}, MagicMock())
        
        assert response['statusCode'] == 500
        assert response['body']['message'] == 'SSL Certificate Monitor encountered a critical error'
        assert response['body']['error'] == 'Critical initialization error'
        assert 'timestamp' in response['body']
    
    @patch('ssl_certificate_monitor.lambda_handler.SSLCertificateMonitor')
    def test_lambda_handler_monitor_execute_exception(self, mock_monitor_class):
        """测试监控器执行异常"""
        mock_monitor = mock_monitor_class.return_value
        mock_monitor.execute.side_effect = Exception("Execution error")
        
        response = lambda_handler({}, MagicMock())
        
        assert response['statusCode'] == 500
        assert response['body']['message'] == 'SSL Certificate Monitor encountered a critical error'
        assert response['body']['error'] == 'Execution error'
    
    @patch.dict(os.environ, {
        'DOMAINS': 'example.com,test.com',
        'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:ssl-alerts',
        'LOG_LEVEL': 'DEBUG'
    })
    @patch('ssl_certificate_monitor.lambda_handler.SSLCertificateMonitor')
    def test_lambda_handler_with_environment_variables(self, mock_monitor_class):
        """测试带环境变量的Lambda处理器"""
        mock_monitor = mock_monitor_class.return_value
        mock_result = MagicMock()
        mock_result.total_domains = 2
        mock_result.successful_checks = 2
        mock_result.failed_checks = 0
        mock_result.expired_domains = []
        mock_result.expiring_domains = []
        mock_result.errors = []
        mock_result.execution_time = 30.0
        
        mock_monitor.execute.return_value = mock_result
        
        response = lambda_handler({}, MagicMock())
        
        assert response['statusCode'] == 200
        assert response['body']['summary']['total_domains'] == 2
        assert response['body']['summary']['success_rate'] == 1.0