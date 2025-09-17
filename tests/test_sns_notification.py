"""
SNS通知服务测试
"""
import pytest
import os
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from botocore.exceptions import ClientError

from ssl_certificate_monitor.services.sns_notification import SNSNotificationService
from ssl_certificate_monitor.models import CertificateInfo


class TestSNSNotificationService:
    """SNS通知服务测试类"""
    
    def setup_method(self):
        """测试前准备"""
        self.topic_arn = "arn:aws:sns:us-east-1:123456789012:ssl-alerts"
        
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    def test_init_with_topic_arn(self, mock_boto3):
        """测试使用指定topic_arn初始化"""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        assert service.topic_arn == self.topic_arn
        assert service.sns_client == mock_client
        mock_boto3.client.assert_called_once_with('sns', region_name='us-east-1')
    
    @patch.dict(os.environ, {'SNS_TOPIC_ARN': 'arn:aws:sns:us-east-1:123456789012:env-topic'})
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    def test_init_from_env(self, mock_boto3):
        """测试从环境变量初始化"""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService()
        
        assert service.topic_arn == 'arn:aws:sns:us-east-1:123456789012:env-topic'
    
    @patch('ssl_certificate_monitor.services.sns_notification.boto3', None)
    def test_init_without_boto3(self):
        """测试没有boto3时的初始化"""
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        assert service.topic_arn == self.topic_arn
        assert service.sns_client is None
    
    def test_format_notification_content_empty(self):
        """测试空证书列表的通知内容格式化"""
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        content = service.format_notification_content([])
        
        assert content == "所有SSL证书状态正常。"
    
    def test_format_notification_content_with_certificates(self):
        """测试包含证书的通知内容格式化"""
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        # 创建测试证书
        expired_cert = CertificateInfo(
            domain="expired.com",
            expiry_date=datetime.now(timezone.utc) - timedelta(days=5),
            days_until_expiry=-5,
            issuer="Test CA",
            is_valid=True
        )
        
        expiring_cert = CertificateInfo(
            domain="expiring.com",
            expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
            days_until_expiry=15,
            issuer="Another CA",
            is_valid=True
        )
        
        content = service.format_notification_content([expired_cert, expiring_cert])
        
        # 验证内容包含关键信息
        assert "SSL证书过期监控报告" in content
        assert "已过期证书:" in content
        assert "即将过期证书" in content
        assert "expired.com" in content
        assert "expiring.com" in content
        assert "已过期: 5 天" in content
        assert "剩余天数: 15 天" in content
        assert "Test CA" in content
        assert "Another CA" in content
    
    def test_format_subject_expired_only(self):
        """测试只有已过期证书的主题格式化"""
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        expired_cert = CertificateInfo(
            domain="expired.com",
            expiry_date=datetime.now(timezone.utc) - timedelta(days=5),
            days_until_expiry=-5,
            issuer="Test CA",
            is_valid=True
        )
        
        subject = service._format_subject([expired_cert])
        
        assert subject == "🚨 SSL证书警报: 1个证书已过期"
    
    def test_format_subject_expiring_only(self):
        """测试只有即将过期证书的主题格式化"""
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        expiring_cert = CertificateInfo(
            domain="expiring.com",
            expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
            days_until_expiry=15,
            issuer="Test CA",
            is_valid=True
        )
        
        subject = service._format_subject([expiring_cert])
        
        assert subject == "⚠️ SSL证书提醒: 1个证书即将过期"
    
    def test_format_subject_mixed(self):
        """测试混合证书状态的主题格式化"""
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        expired_cert = CertificateInfo(
            domain="expired.com",
            expiry_date=datetime.now(timezone.utc) - timedelta(days=5),
            days_until_expiry=-5,
            issuer="Test CA",
            is_valid=True
        )
        
        expiring_cert = CertificateInfo(
            domain="expiring.com",
            expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
            days_until_expiry=15,
            issuer="Test CA",
            is_valid=True
        )
        
        subject = service._format_subject([expired_cert, expiring_cert])
        
        assert subject == "🚨 SSL证书警报: 1个已过期, 1个即将过期"
    
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    def test_validate_configuration_valid(self, mock_boto3):
        """测试有效配置验证"""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        assert service._validate_configuration() is True
    
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    def test_validate_configuration_no_topic_arn(self, mock_boto3):
        """测试缺少topic_arn的配置验证"""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService(topic_arn=None)
        
        assert service._validate_configuration() is False
    
    def test_validate_configuration_no_client(self):
        """测试缺少SNS客户端的配置验证"""
        service = SNSNotificationService(topic_arn=self.topic_arn)
        service.sns_client = None
        
        assert service._validate_configuration() is False
    
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    def test_send_expiry_notification_empty_list(self, mock_boto3):
        """测试发送空证书列表通知"""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        result = service.send_expiry_notification([])
        
        assert result is True
        mock_client.publish.assert_not_called()
    
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    def test_send_expiry_notification_success(self, mock_boto3):
        """测试成功发送通知"""
        mock_client = MagicMock()
        mock_client.publish.return_value = {'MessageId': 'test-message-id'}
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        expiring_cert = CertificateInfo(
            domain="expiring.com",
            expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
            days_until_expiry=15,
            issuer="Test CA",
            is_valid=True
        )
        
        result = service.send_expiry_notification([expiring_cert])
        
        assert result is True
        mock_client.publish.assert_called_once()
        
        # 验证调用参数
        call_args = mock_client.publish.call_args
        assert call_args[1]['TopicArn'] == self.topic_arn
        assert 'Subject' in call_args[1]
        assert 'Message' in call_args[1]
    
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    def test_send_expiry_notification_client_error(self, mock_boto3):
        """测试SNS客户端错误"""
        mock_client = MagicMock()
        mock_client.publish.side_effect = ClientError(
            {'Error': {'Code': 'NotFound', 'Message': 'Topic not found'}},
            'Publish'
        )
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        expiring_cert = CertificateInfo(
            domain="expiring.com",
            expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
            days_until_expiry=15,
            issuer="Test CA",
            is_valid=True
        )
        
        result = service.send_expiry_notification([expiring_cert])
        
        assert result is False
    
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    def test_test_connection_success(self, mock_boto3):
        """测试成功的连接测试"""
        mock_client = MagicMock()
        mock_client.get_topic_attributes.return_value = {'Attributes': {}}
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        result = service.test_connection()
        
        assert result is True
        mock_client.get_topic_attributes.assert_called_once_with(TopicArn=self.topic_arn)
    
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    def test_test_connection_failure(self, mock_boto3):
        """测试失败的连接测试"""
        mock_client = MagicMock()
        mock_client.get_topic_attributes.side_effect = ClientError(
            {'Error': {'Code': 'NotFound', 'Message': 'Topic not found'}},
            'GetTopicAttributes'
        )
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        result = service.test_connection()
        
        assert result is False
    
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    def test_get_configuration_status(self, mock_boto3):
        """测试获取配置状态"""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService(topic_arn=self.topic_arn, region_name='us-west-2')
        
        status = service.get_configuration_status()
        
        assert status['boto3_available'] is True
        assert status['sns_client_initialized'] is True
        assert status['topic_arn_configured'] is True
        assert status['topic_arn'] == self.topic_arn
        assert status['region_name'] == 'us-west-2'
        assert status['configuration_valid'] is True
    
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    @patch('time.sleep')
    def test_publish_with_retry_success_after_retry(self, mock_sleep, mock_boto3):
        """测试重试后成功发送"""
        mock_client = MagicMock()
        # 第一次失败，第二次成功
        mock_client.publish.side_effect = [
            ClientError({'Error': {'Code': 'Throttling', 'Message': 'Rate exceeded'}}, 'Publish'),
            {'MessageId': 'test-message-id'}
        ]
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        result = service._publish_with_retry("Test Subject", "Test Message")
        
        assert result is True
        assert mock_client.publish.call_count == 2
        mock_sleep.assert_called_once_with(1)  # 第一次重试等待1秒
    
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    @patch('time.sleep')
    def test_publish_with_retry_max_retries_exceeded(self, mock_sleep, mock_boto3):
        """测试超过最大重试次数"""
        mock_client = MagicMock()
        mock_client.publish.side_effect = ClientError(
            {'Error': {'Code': 'Throttling', 'Message': 'Rate exceeded'}}, 'Publish'
        )
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        result = service._publish_with_retry("Test Subject", "Test Message", max_retries=2)
        
        assert result is False
        assert mock_client.publish.call_count == 3  # 初始尝试 + 2次重试
        assert mock_sleep.call_count == 2
    
    def test_is_retryable_error(self):
        """测试可重试错误判断"""
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        # 可重试的错误
        assert service._is_retryable_error('Throttling') is True
        assert service._is_retryable_error('ServiceUnavailable') is True
        assert service._is_retryable_error('InternalError') is True
        assert service._is_retryable_error('RequestTimeout') is True
        
        # 不可重试的错误
        assert service._is_retryable_error('NotFound') is False
        assert service._is_retryable_error('AccessDenied') is False
        assert service._is_retryable_error('InvalidParameter') is False
    
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    def test_send_batch_notifications_small_batch(self, mock_boto3):
        """测试小批量通知发送"""
        mock_client = MagicMock()
        mock_client.publish.return_value = {'MessageId': 'test-message-id'}
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        # 创建少量证书（少于批量大小）
        certificates = [
            CertificateInfo(
                domain=f"test{i}.com",
                expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
                days_until_expiry=15,
                issuer="Test CA",
                is_valid=True
            ) for i in range(3)
        ]
        
        result = service.send_batch_notifications(certificates, batch_size=10)
        
        assert result is True
        assert mock_client.publish.call_count == 1  # 只发送一次
    
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    def test_send_batch_notifications_multiple_batches(self, mock_boto3):
        """测试多批次通知发送"""
        mock_client = MagicMock()
        mock_client.publish.return_value = {'MessageId': 'test-message-id'}
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        # 创建大量证书（超过批量大小）
        certificates = [
            CertificateInfo(
                domain=f"test{i}.com",
                expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
                days_until_expiry=15,
                issuer="Test CA",
                is_valid=True
            ) for i in range(25)
        ]
        
        result = service.send_batch_notifications(certificates, batch_size=10)
        
        assert result is True
        assert mock_client.publish.call_count == 3  # 25个证书分3批发送
    
    @patch('ssl_certificate_monitor.services.sns_notification.boto3')
    def test_send_batch_notifications_partial_failure(self, mock_boto3):
        """测试批量发送部分失败"""
        mock_client = MagicMock()
        # 第一批成功，第二批失败，第三批成功
        mock_client.publish.side_effect = [
            {'MessageId': 'test-message-id-1'},
            ClientError({'Error': {'Code': 'NotFound', 'Message': 'Topic not found'}}, 'Publish'),
            {'MessageId': 'test-message-id-3'}
        ]
        mock_boto3.client.return_value = mock_client
        
        service = SNSNotificationService(topic_arn=self.topic_arn)
        
        # 创建大量证书
        certificates = [
            CertificateInfo(
                domain=f"test{i}.com",
                expiry_date=datetime.now(timezone.utc) + timedelta(days=15),
                days_until_expiry=15,
                issuer="Test CA",
                is_valid=True
            ) for i in range(25)
        ]
        
        result = service.send_batch_notifications(certificates, batch_size=10)
        
        assert result is False  # 因为有一批失败
        assert mock_client.publish.call_count == 3