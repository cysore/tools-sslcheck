"""
日志服务测试
"""
import pytest
import os
import logging
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from io import StringIO

from ssl_certificate_monitor.services.logger import LoggerService
from ssl_certificate_monitor.models import CertificateInfo


class TestLoggerService:
    """日志服务测试类"""
    
    def setup_method(self):
        """测试前准备"""
        # 创建一个独立的日志服务实例
        self.logger_service = LoggerService(logger_name="test_logger")
        
        # 创建一个字符串流来捕获日志输出
        self.log_stream = StringIO()
        handler = logging.StreamHandler(self.log_stream)
        handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        
        # 清除现有处理器并添加测试处理器
        self.logger_service.logger.handlers.clear()
        self.logger_service.logger.addHandler(handler)
        self.logger_service.logger.setLevel(logging.DEBUG)
    
    def teardown_method(self):
        """测试后清理"""
        self.logger_service.reset_stats()
    
    def get_log_output(self) -> str:
        """获取日志输出"""
        return self.log_stream.getvalue()
    
    def test_init_default_config(self):
        """测试默认配置初始化"""
        service = LoggerService()
        
        assert service.logger_name == "ssl_certificate_monitor"
        assert service.log_level == "INFO"
        assert service.logger is not None
    
    @patch.dict(os.environ, {'LOG_LEVEL': 'DEBUG'})
    def test_init_with_env_log_level(self):
        """测试从环境变量读取日志级别"""
        service = LoggerService()
        
        assert service.log_level == "DEBUG"
    
    def test_init_with_custom_config(self):
        """测试自定义配置初始化"""
        service = LoggerService(logger_name="custom_logger", log_level="WARNING")
        
        assert service.logger_name == "custom_logger"
        assert service.log_level == "WARNING"
    
    def test_log_check_start(self):
        """测试记录检查开始"""
        self.logger_service.log_check_start(5)
        
        log_output = self.get_log_output()
        assert "开始SSL证书检查，共 5 个域名" in log_output
        assert "检查开始时间:" in log_output
        
        # 验证统计信息
        assert self.logger_service.execution_stats['total_domains'] == 5
        assert self.logger_service.execution_stats['start_time'] is not None
    
    def test_log_certificate_info_valid_normal(self):
        """测试记录正常证书信息"""
        cert_info = CertificateInfo(
            domain="example.com",
            expiry_date=datetime.now(timezone.utc) + timedelta(days=60),
            days_until_expiry=60,
            issuer="Test CA",
            is_valid=True
        )
        
        self.logger_service.log_certificate_info("example.com", cert_info)
        
        log_output = self.get_log_output()
        assert "证书正常 - 域名: example.com" in log_output
        assert "剩余天数: 60 天" in log_output
        assert "颁发者: Test CA" in log_output
        
        # 验证统计信息
        assert self.logger_service.execution_stats['successful_checks'] == 1
        assert self.logger_service.execution_stats['failed_checks'] == 0
    
    def test_log_certificate_info_expiring_soon(self):
        """测试记录即将过期证书信息"""
        cert_info = CertificateInfo(
            domain="expiring.com",
            expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
            days_until_expiry=15,
            issuer="Test CA",
            is_valid=True
        )
        
        self.logger_service.log_certificate_info("expiring.com", cert_info)
        
        log_output = self.get_log_output()
        assert "WARNING - 证书即将过期 - 域名: expiring.com" in log_output
        assert "剩余天数: 15 天" in log_output
    
    def test_log_certificate_info_expired(self):
        """测试记录已过期证书信息"""
        cert_info = CertificateInfo(
            domain="expired.com",
            expiry_date=datetime.now(timezone.utc) - timedelta(days=5),
            days_until_expiry=-5,
            issuer="Test CA",
            is_valid=True
        )
        
        self.logger_service.log_certificate_info("expired.com", cert_info)
        
        log_output = self.get_log_output()
        assert "WARNING - 证书已过期 - 域名: expired.com" in log_output
        assert "已过期: 5 天" in log_output
    
    def test_log_certificate_info_invalid(self):
        """测试记录无效证书信息"""
        cert_info = CertificateInfo(
            domain="invalid.com",
            expiry_date=datetime.now(timezone.utc),
            days_until_expiry=-1,
            issuer="Unknown",
            is_valid=False,
            error_message="Connection failed"
        )
        
        self.logger_service.log_certificate_info("invalid.com", cert_info)
        
        log_output = self.get_log_output()
        assert "ERROR - 证书检查失败 - 域名: invalid.com" in log_output
        assert "错误: Connection failed" in log_output
        
        # 验证统计信息
        assert self.logger_service.execution_stats['successful_checks'] == 0
        assert self.logger_service.execution_stats['failed_checks'] == 1
    
    def test_log_error(self):
        """测试记录错误信息"""
        error = ValueError("Test error message")
        
        self.logger_service.log_error("test.com", error)
        
        log_output = self.get_log_output()
        assert "ERROR - 域名 test.com 检查时发生错误: ValueError: Test error message" in log_output
        
        # 验证错误统计
        assert len(self.logger_service.execution_stats['errors']) == 1
        error_info = self.logger_service.execution_stats['errors'][0]
        assert error_info['domain'] == "test.com"
        assert error_info['error_type'] == "ValueError"
        assert error_info['error_message'] == "Test error message"
    
    def test_log_check_end(self):
        """测试记录检查结束"""
        # 先开始检查
        self.logger_service.log_check_start(3)
        
        # 模拟一些检查结果
        self.logger_service.execution_stats['successful_checks'] = 2
        self.logger_service.execution_stats['failed_checks'] = 1
        
        # 结束检查
        self.logger_service.log_check_end()
        
        log_output = self.get_log_output()
        assert "SSL证书检查完成" in log_output
        assert "检查结束时间:" in log_output
        assert "总执行时间:" in log_output
        assert "检查统计: 总计 3 个域名, 成功 2 个, 失败 1 个" in log_output
        
        # 验证结束时间被设置
        assert self.logger_service.execution_stats['end_time'] is not None
    
    def test_log_notification_sent_success(self):
        """测试记录成功的通知发送"""
        self.logger_service.log_notification_sent("SNS", 1, True)
        
        log_output = self.get_log_output()
        assert "INFO - SNS 通知发送成功，接收者数量: 1" in log_output
    
    def test_log_notification_sent_failure(self):
        """测试记录失败的通知发送"""
        self.logger_service.log_notification_sent("SNS", 1, False)
        
        log_output = self.get_log_output()
        assert "ERROR - SNS 通知发送失败，接收者数量: 1" in log_output
    
    def test_log_configuration_info(self):
        """测试记录配置信息"""
        config = {
            'domains': 'example.com,test.com',
            'sns_topic_arn': 'arn:aws:sns:us-east-1:123456789012:ssl-alerts',
            'log_level': 'INFO',
            'password': 'secret123'
        }
        
        self.logger_service.log_configuration_info(config)
        
        log_output = self.get_log_output()
        assert "系统配置信息:" in log_output
        assert "domains: example.com,test.com" in log_output
        assert "log_level: INFO" in log_output
        
        # 验证敏感信息被隐藏
        assert "secret123" not in log_output
        assert "password: sec***" in log_output
        assert "arn:aws:sns:***:123456789012:ssl-alerts" in log_output
    
    def test_sanitize_config(self):
        """测试配置信息清理"""
        config = {
            'normal_setting': 'normal_value',
            'password': 'secret123',
            'api_key': 'key456',
            'sns_topic_arn': 'arn:aws:sns:us-east-1:123456789012:ssl-alerts',
            'short_secret': 'ab',
            'domains': 'example.com'
        }
        
        safe_config = self.logger_service._sanitize_config(config)
        
        assert safe_config['normal_setting'] == 'normal_value'
        assert safe_config['domains'] == 'example.com'
        assert safe_config['password'] == 'sec***'
        assert safe_config['api_key'] == 'key***'
        assert safe_config['sns_topic_arn'] == 'arn:aws:sns:***:123456789012:ssl-alerts'
        assert safe_config['short_secret'] == '***'
    
    def test_get_execution_summary(self):
        """测试获取执行摘要"""
        # 设置一些测试数据
        start_time = datetime.now(timezone.utc)
        self.logger_service.execution_stats.update({
            'start_time': start_time,
            'end_time': start_time + timedelta(seconds=30),
            'total_domains': 5,
            'successful_checks': 3,
            'failed_checks': 2,
            'errors': [
                {'domain': 'error1.com', 'error_type': 'ValueError', 'error_message': 'Test error'}
            ]
        })
        
        summary = self.logger_service.get_execution_summary()
        
        assert summary['duration_seconds'] == 30.0
        assert summary['total_domains'] == 5
        assert summary['successful_checks'] == 3
        assert summary['failed_checks'] == 2
        assert summary['success_rate'] == 0.6
        assert summary['error_count'] == 1
        assert len(summary['errors']) == 1
    
    def test_log_execution_summary(self):
        """测试记录执行摘要"""
        # 设置一些测试数据
        start_time = datetime.now(timezone.utc)
        self.logger_service.execution_stats.update({
            'start_time': start_time,
            'end_time': start_time + timedelta(seconds=45),
            'total_domains': 10,
            'successful_checks': 8,
            'failed_checks': 2,
            'errors': [
                {'domain': 'error1.com', 'error_type': 'ValueError', 'error_message': 'Test error 1'},
                {'domain': 'error2.com', 'error_type': 'ConnectionError', 'error_message': 'Test error 2'}
            ]
        })
        
        self.logger_service.log_execution_summary()
        
        log_output = self.get_log_output()
        assert "执行摘要" in log_output
        assert "执行时长: 45.00 秒" in log_output
        assert "总域名数: 10" in log_output
        assert "成功检查: 8" in log_output
        assert "失败检查: 2" in log_output
        assert "成功率: 80.0%" in log_output
        assert "错误数量: 2" in log_output
        assert "error1.com - ValueError: Test error 1" in log_output
    
    def test_reset_stats(self):
        """测试重置统计信息"""
        # 设置一些数据
        self.logger_service.execution_stats.update({
            'start_time': datetime.now(timezone.utc),
            'total_domains': 5,
            'successful_checks': 3,
            'errors': [{'domain': 'test.com', 'error': 'test'}]
        })
        
        # 重置
        self.logger_service.reset_stats()
        
        # 验证重置结果
        assert self.logger_service.execution_stats['start_time'] is None
        assert self.logger_service.execution_stats['total_domains'] == 0
        assert self.logger_service.execution_stats['successful_checks'] == 0
        assert self.logger_service.execution_stats['errors'] == []
    
    def test_multiple_certificate_logging(self):
        """测试多个证书的日志记录"""
        certificates = [
            CertificateInfo("normal.com", datetime.now(timezone.utc) + timedelta(days=60), 60, "CA1", True),
            CertificateInfo("expiring.com", datetime.now(timezone.utc) + timedelta(days=15), 15, "CA2", True),
            CertificateInfo("expired.com", datetime.now(timezone.utc) - timedelta(days=5), -5, "CA3", True),
            CertificateInfo("invalid.com", datetime.now(timezone.utc), -1, "Unknown", False, "Connection failed")
        ]
        
        for cert in certificates:
            self.logger_service.log_certificate_info(cert.domain, cert)
        
        # 验证统计信息
        assert self.logger_service.execution_stats['successful_checks'] == 3
        assert self.logger_service.execution_stats['failed_checks'] == 1
        
        log_output = self.get_log_output()
        assert "证书正常 - 域名: normal.com" in log_output
        assert "证书即将过期 - 域名: expiring.com" in log_output
        assert "证书已过期 - 域名: expired.com" in log_output
        assert "证书检查失败 - 域名: invalid.com" in log_output