"""
SNS通知服务
"""
import os
import json
from typing import List, Optional
import logging
from datetime import datetime

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None

from ..interfaces import NotificationServiceInterface
from ..models import CertificateInfo


class SNSNotificationService(NotificationServiceInterface):
    """SNS通知服务实现"""
    
    def __init__(self, topic_arn: Optional[str] = None, region_name: Optional[str] = None):
        """
        初始化SNS通知服务
        
        Args:
            topic_arn: SNS主题ARN，如果为None则从环境变量读取
            region_name: AWS区域名称，如果为None则自动检测
        """
        self.topic_arn = topic_arn or os.getenv('SNS_TOPIC_ARN')
        
        # 自动检测区域
        if region_name:
            self.region_name = region_name
        elif self.topic_arn and 'arn:aws:sns:' in self.topic_arn:
            # 从SNS ARN中提取区域
            self.region_name = self.topic_arn.split(':')[3]
        else:
            # 默认区域
            self.region_name = os.getenv('AWS_REGION', 'us-east-1')
            
        self.logger = logging.getLogger(__name__)
        
        # 初始化SNS客户端
        self.sns_client = None
        if boto3:
            try:
                self.sns_client = boto3.client('sns', region_name=self.region_name)
                self.logger.info(f"SNS客户端初始化成功，区域: {self.region_name}")
            except Exception as e:
                self.logger.error(f"初始化SNS客户端失败: {str(e)}")
        else:
            self.logger.warning("boto3未安装，SNS功能不可用")
    
    def send_expiry_notification(self, expiring_domains: List[CertificateInfo]) -> bool:
        """
        发送证书过期通知
        
        Args:
            expiring_domains: 即将过期的证书列表
            
        Returns:
            bool: 发送是否成功
        """
        if not expiring_domains:
            self.logger.info("没有即将过期的证书，跳过通知发送")
            return True
        
        if not self._validate_configuration():
            return False
        
        # 格式化通知内容
        subject = self._format_subject(expiring_domains)
        message = self.format_notification_content(expiring_domains)
        
        # 使用重试机制发送消息
        return self._publish_with_retry(subject, message)
    
    def _publish_with_retry(self, subject: str, message: str, max_retries: int = 3) -> bool:
        """
        带重试机制的SNS消息发布
        
        Args:
            subject: 消息主题
            message: 消息内容
            max_retries: 最大重试次数
            
        Returns:
            bool: 发送是否成功
        """
        import time
        
        for attempt in range(max_retries + 1):
            try:
                # 发送SNS消息
                response = self.sns_client.publish(
                    TopicArn=self.topic_arn,
                    Subject=subject,
                    Message=message
                )
                
                message_id = response.get('MessageId')
                self.logger.info(f"SNS通知发送成功，MessageId: {message_id}")
                return True
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_message = e.response['Error']['Message']
                
                # 检查是否是可重试的错误
                if self._is_retryable_error(error_code) and attempt < max_retries:
                    wait_time = 2 ** attempt  # 指数退避
                    self.logger.warning(
                        f"SNS发送失败 (尝试 {attempt + 1}/{max_retries + 1}) - {error_code}: {error_message}，"
                        f"{wait_time}秒后重试"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"SNS发送失败 - {error_code}: {error_message}")
                    return False
                    
            except Exception as e:
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    self.logger.warning(
                        f"发送SNS通知时发生错误 (尝试 {attempt + 1}/{max_retries + 1}): {str(e)}，"
                        f"{wait_time}秒后重试"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"发送SNS通知时发生未知错误: {str(e)}")
                    return False
        
        return False
    
    def _is_retryable_error(self, error_code: str) -> bool:
        """
        判断错误是否可重试
        
        Args:
            error_code: AWS错误代码
            
        Returns:
            bool: 是否可重试
        """
        retryable_errors = {
            'Throttling',
            'ServiceUnavailable',
            'InternalError',
            'RequestTimeout'
        }
        return error_code in retryable_errors
    
    def format_notification_content(self, domains: List[CertificateInfo]) -> str:
        """
        格式化通知内容
        
        Args:
            domains: 证书信息列表
            
        Returns:
            str: 格式化的通知内容
        """
        if not domains:
            return "所有SSL证书状态正常。"
        
        # 分类证书
        expired_certs = [cert for cert in domains if cert.is_expired]
        expiring_certs = [cert for cert in domains if cert.is_expiring_soon and not cert.is_expired]
        
        lines = [
            "SSL证书过期监控报告",
            "=" * 30,
            f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]
        
        # 已过期证书
        if expired_certs:
            lines.extend([
                "🚨 已过期证书:",
                ""
            ])
            for cert in expired_certs:
                lines.append(f"• {cert.domain}")
                lines.append(f"  过期时间: {cert.expiry_date.strftime('%Y-%m-%d %H:%M:%S')}")
                lines.append(f"  已过期: {abs(cert.days_until_expiry)} 天")
                lines.append(f"  颁发者: {cert.issuer}")
                lines.append("")
        
        # 即将过期证书
        if expiring_certs:
            lines.extend([
                "⚠️  即将过期证书 (30天内):",
                ""
            ])
            for cert in expiring_certs:
                lines.append(f"• {cert.domain}")
                lines.append(f"  过期时间: {cert.expiry_date.strftime('%Y-%m-%d %H:%M:%S')}")
                lines.append(f"  剩余天数: {cert.days_until_expiry} 天")
                lines.append(f"  颁发者: {cert.issuer}")
                lines.append("")
        
        # 添加建议
        lines.extend([
            "建议操作:",
            "1. 立即续期已过期的证书",
            "2. 计划续期即将过期的证书",
            "3. 更新证书后重新部署相关服务",
            "",
            "此消息由SSL证书监控系统自动发送。"
        ])
        
        return "\n".join(lines)
    
    def _format_subject(self, domains: List[CertificateInfo]) -> str:
        """
        格式化邮件主题
        
        Args:
            domains: 证书信息列表
            
        Returns:
            str: 邮件主题
        """
        expired_count = len([cert for cert in domains if cert.is_expired])
        expiring_count = len([cert for cert in domains if cert.is_expiring_soon and not cert.is_expired])
        
        if expired_count > 0 and expiring_count > 0:
            return f"🚨 SSL证书警报: {expired_count}个已过期, {expiring_count}个即将过期"
        elif expired_count > 0:
            return f"🚨 SSL证书警报: {expired_count}个证书已过期"
        elif expiring_count > 0:
            return f"⚠️ SSL证书提醒: {expiring_count}个证书即将过期"
        else:
            return "SSL证书状态报告"
    
    def _validate_configuration(self) -> bool:
        """
        验证配置是否正确
        
        Returns:
            bool: 配置是否有效
        """
        if not self.sns_client:
            self.logger.error("SNS客户端未初始化")
            return False
        
        if not self.topic_arn:
            self.logger.error("SNS主题ARN未配置")
            return False
        
        return True
    
    def test_connection(self) -> bool:
        """
        测试SNS连接
        
        Returns:
            bool: 连接是否成功
        """
        if not self._validate_configuration():
            return False
        
        try:
            # 尝试获取主题属性来测试连接
            self.sns_client.get_topic_attributes(TopicArn=self.topic_arn)
            self.logger.info("SNS连接测试成功")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            self.logger.error(f"SNS连接测试失败 - {error_code}: {error_message}")
            return False
            
        except Exception as e:
            self.logger.error(f"SNS连接测试时发生错误: {str(e)}")
            return False
    
    def get_configuration_status(self) -> dict:
        """
        获取配置状态
        
        Returns:
            dict: 配置状态信息
        """
        return {
            'boto3_available': boto3 is not None,
            'sns_client_initialized': self.sns_client is not None,
            'topic_arn_configured': bool(self.topic_arn),
            'topic_arn': self.topic_arn,
            'region_name': self.region_name,
            'configuration_valid': self._validate_configuration()
        }
    
    def send_batch_notifications(self, expiring_domains: List[CertificateInfo], batch_size: int = 10) -> bool:
        """
        批量发送通知（当域名数量很多时）
        
        Args:
            expiring_domains: 即将过期的证书列表
            batch_size: 每批处理的域名数量
            
        Returns:
            bool: 所有批次是否都发送成功
        """
        if not expiring_domains:
            return True
        
        if len(expiring_domains) <= batch_size:
            return self.send_expiry_notification(expiring_domains)
        
        # 分批发送
        success_count = 0
        total_batches = (len(expiring_domains) + batch_size - 1) // batch_size
        
        for i in range(0, len(expiring_domains), batch_size):
            batch = expiring_domains[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            self.logger.info(f"发送第 {batch_num}/{total_batches} 批通知，包含 {len(batch)} 个域名")
            
            if self.send_expiry_notification(batch):
                success_count += 1
            else:
                self.logger.error(f"第 {batch_num} 批通知发送失败")
        
        success_rate = success_count / total_batches
        self.logger.info(f"批量发送完成，成功率: {success_rate:.1%} ({success_count}/{total_batches})")
        
        return success_count == total_batches
    
    def send_status_report(self, all_domains: List[CertificateInfo], execution_summary: dict) -> bool:
        """
        发送完整的SSL证书状态报告
        
        Args:
            all_domains: 所有检查的域名证书信息
            execution_summary: 执行摘要信息
            
        Returns:
            bool: 发送是否成功
        """
        if not self._validate_configuration():
            return False
        
        # 格式化报告内容
        subject = self._format_status_subject(all_domains, execution_summary)
        message = self.format_status_report_content(all_domains, execution_summary)
        
        # 使用重试机制发送消息
        return self._publish_with_retry(subject, message)
    
    def _format_status_subject(self, all_domains: List[CertificateInfo], execution_summary: dict) -> str:
        """
        格式化状态报告邮件主题
        
        Args:
            all_domains: 所有域名证书信息
            execution_summary: 执行摘要
            
        Returns:
            str: 邮件主题
        """
        total_domains = len(all_domains)
        expired_count = len([cert for cert in all_domains if cert.is_expired])
        expiring_count = len([cert for cert in all_domains if cert.is_expiring_soon and not cert.is_expired])
        success_rate = execution_summary.get('success_rate', 0)
        
        if expired_count > 0:
            return f"🚨 SSL证书日报: {expired_count}个已过期 | {total_domains}个域名 | {success_rate*100:.0f}%成功率"
        elif expiring_count > 0:
            return f"⚠️ SSL证书日报: {expiring_count}个即将过期 | {total_domains}个域名 | {success_rate*100:.0f}%成功率"
        else:
            return f"✅ SSL证书日报: 全部正常 | {total_domains}个域名 | {success_rate*100:.0f}%成功率"
    
    def format_status_report_content(self, all_domains: List[CertificateInfo], execution_summary: dict) -> str:
        """
        格式化完整状态报告内容
        
        Args:
            all_domains: 所有域名证书信息
            execution_summary: 执行摘要
            
        Returns:
            str: 格式化的报告内容
        """
        # 分类证书
        failed_certs = [cert for cert in all_domains if not cert.is_valid]
        valid_certs = [cert for cert in all_domains if cert.is_valid]
        
        expired_certs = [cert for cert in valid_certs if cert.is_expired]
        expiring_certs = [cert for cert in valid_certs if cert.is_expiring_soon and not cert.is_expired]
        normal_certs = [cert for cert in valid_certs if not cert.is_expiring_soon and not cert.is_expired]
        
        lines = [
            "SSL证书监控日报",
            "=" * 40,
            f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"执行时长: {execution_summary.get('duration_seconds', 0):.2f} 秒",
            f"总域名数: {len(all_domains)}",
            f"成功检查: {execution_summary.get('successful_checks', 0)}",
            f"失败检查: {execution_summary.get('failed_checks', 0)}",
            f"成功率: {execution_summary.get('success_rate', 0)*100:.1f}%",
            ""
        ]
        
        # 已过期证书（紧急）
        if expired_certs:
            lines.extend([
                "🚨 已过期证书 (需要立即处理):",
                "-" * 30
            ])
            for cert in expired_certs:
                lines.append(f"• {cert.domain}")
                lines.append(f"  过期时间: {cert.expiry_date.strftime('%Y-%m-%d')}")
                lines.append(f"  已过期: {abs(cert.days_until_expiry)} 天")
                lines.append(f"  颁发者: {cert.issuer}")
                lines.append("")
        
        # 即将过期证书（警告）
        if expiring_certs:
            lines.extend([
                "⚠️  即将过期证书 (30天内):",
                "-" * 30
            ])
            for cert in expiring_certs:
                lines.append(f"• {cert.domain}")
                lines.append(f"  过期时间: {cert.expiry_date.strftime('%Y-%m-%d')}")
                lines.append(f"  剩余天数: {cert.days_until_expiry} 天")
                lines.append(f"  颁发者: {cert.issuer}")
                lines.append("")
        
        # 检查失败的证书（错误）
        if failed_certs:
            lines.extend([
                "❌ 检查失败的证书:",
                "-" * 30
            ])
            for cert in failed_certs:
                lines.append(f"• {cert.domain}")
                lines.append(f"  错误: {cert.error_message}")
                lines.append("")
        
        # 正常证书（信息）
        if normal_certs:
            lines.extend([
                "✅ 正常证书状态:",
                "-" * 30
            ])
            for cert in normal_certs:
                lines.append(f"• {cert.domain} - {cert.days_until_expiry}天后过期 ({cert.expiry_date.strftime('%Y-%m-%d')})")
            lines.append("")
        
        # 添加统计摘要
        lines.extend([
            "📊 统计摘要:",
            "-" * 30,
            f"🚨 已过期: {len(expired_certs)} 个",
            f"⚠️  即将过期: {len(expiring_certs)} 个",
            f"✅ 正常: {len(normal_certs)} 个",
            f"❌ 检查失败: {len(failed_certs)} 个",
            ""
        ])
        
        # 添加建议操作
        if expired_certs or expiring_certs or failed_certs:
            lines.extend([
                "🔧 建议操作:",
                "-" * 30
            ])
            if expired_certs:
                lines.append("1. 立即续期已过期的证书")
            if expiring_certs:
                lines.append("2. 计划续期即将过期的证书")
            if failed_certs:
                lines.append("3. 检查失败域名的网络连接和DNS配置")
            if expired_certs or expiring_certs:
                lines.append("4. 更新证书后重新部署相关服务")
                lines.append("5. 检查证书自动续期配置")
            lines.append("")
        
        lines.extend([
            "---",
            "此报告由SSL证书监控系统自动生成",
            f"下次检查时间: 明天同一时间",
            "如有问题请检查CloudWatch日志"
        ])
        
        return "\n".join(lines)