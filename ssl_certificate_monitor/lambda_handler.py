"""
AWS Lambda函数入口点
"""
import json
import os
from typing import Dict, Any, List
from datetime import datetime, timezone

from .services.domain_config import DomainConfigManager
from .services.ssl_checker import SSLCertificateChecker
from .services.sns_notification import SNSNotificationService
from .services.logger import LoggerService
from .services.expiry_calculator import ExpiryCalculator
from .models import CertificateInfo, CheckResult


class SSLCertificateMonitor:
    """SSL证书监控器主类"""
    
    def __init__(self):
        """初始化监控器"""
        # 初始化服务组件
        self.logger_service = LoggerService()
        self.domain_manager = DomainConfigManager()
        self.ssl_checker = SSLCertificateChecker()
        self.notification_service = SNSNotificationService()
        self.expiry_calculator = ExpiryCalculator()
        
        # 记录配置信息
        self._log_configuration()
    
    def _log_configuration(self):
        """记录系统配置信息"""
        config = {
            'domains_env_var': os.getenv('DOMAINS', ''),
            'sns_topic_arn': os.getenv('SNS_TOPIC_ARN', ''),
            'log_level': os.getenv('LOG_LEVEL', 'INFO'),
            'lambda_function_name': os.getenv('AWS_LAMBDA_FUNCTION_NAME', 'unknown'),
            'lambda_memory_size': os.getenv('AWS_LAMBDA_FUNCTION_MEMORY_SIZE', 'unknown'),
            'lambda_timeout': os.getenv('AWS_LAMBDA_FUNCTION_TIMEOUT', 'unknown')
        }
        
        self.logger_service.log_configuration_info(config)
    
    def execute(self) -> CheckResult:
        """
        执行SSL证书检查
        
        Returns:
            CheckResult: 检查结果
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # 获取域名列表
            domains = self.domain_manager.get_domains()
            
            if not domains:
                self.logger_service.logger.warning("没有找到要检查的域名")
                return CheckResult(
                    total_domains=0,
                    successful_checks=0,
                    failed_checks=0,
                    expiring_domains=[],
                    expired_domains=[],
                    errors=["没有找到要检查的域名"],
                    execution_time=0.0
                )
            
            # 开始检查
            self.logger_service.log_check_start(len(domains))
            
            # 批处理检查域名证书
            certificate_results = self._check_certificates_batch(domains)
            
            # 分析结果
            categorized = self.expiry_calculator.categorize_certificates(certificate_results)
            
            # 发送通知（如果有即将过期或已过期的证书）
            notification_sent = self._send_notifications(categorized)
            
            # 发送完整状态报告（每次都发送）
            self._send_status_report(certificate_results)
            
            # 结束检查
            self.logger_service.log_check_end()
            
            # 计算执行时间
            end_time = datetime.now(timezone.utc)
            execution_time = (end_time - start_time).total_seconds()
            
            # 创建检查结果
            result = CheckResult(
                total_domains=len(domains),
                successful_checks=len([cert for cert in certificate_results if cert.is_valid]),
                failed_checks=len([cert for cert in certificate_results if not cert.is_valid]),
                expiring_domains=categorized['expiring_soon'],
                expired_domains=categorized['expired'],
                errors=[cert.error_message for cert in certificate_results if cert.error_message],
                execution_time=execution_time
            )
            
            # 记录执行摘要
            self.logger_service.log_execution_summary()
            
            return result
            
        except Exception as e:
            self.logger_service.logger.error(f"执行SSL证书检查时发生严重错误: {str(e)}")
            end_time = datetime.now(timezone.utc)
            execution_time = (end_time - start_time).total_seconds()
            
            return CheckResult(
                total_domains=0,
                successful_checks=0,
                failed_checks=0,
                expiring_domains=[],
                expired_domains=[],
                errors=[str(e)],
                execution_time=execution_time
            )
    
    def _check_certificates_batch(self, domains: List[str], batch_size: int = 10) -> List[CertificateInfo]:
        """
        批处理检查证书
        
        Args:
            domains: 域名列表
            batch_size: 批处理大小
            
        Returns:
            List[CertificateInfo]: 证书信息列表
        """
        certificate_results = []
        total_batches = (len(domains) + batch_size - 1) // batch_size
        
        for i in range(0, len(domains), batch_size):
            batch = domains[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            self.logger_service.logger.info(f"处理第 {batch_num}/{total_batches} 批域名，包含 {len(batch)} 个域名")
            
            # 处理当前批次
            for domain in batch:
                try:
                    cert_info = self.ssl_checker.check_certificate(domain)
                    certificate_results.append(cert_info)
                    self.logger_service.log_certificate_info(domain, cert_info)
                    
                except Exception as e:
                    self.logger_service.log_error(domain, e)
                    # 创建一个错误的证书信息对象
                    error_cert = CertificateInfo(
                        domain=domain,
                        expiry_date=datetime.now(timezone.utc),
                        days_until_expiry=-1,
                        issuer="Unknown",
                        is_valid=False,
                        error_message=str(e)
                    )
                    certificate_results.append(error_cert)
            
            # 批次间短暂暂停，避免过度负载
            if batch_num < total_batches:
                import time
                time.sleep(0.1)
        
        return certificate_results
    
    def _send_notifications(self, categorized: dict) -> bool:
        """
        发送通知
        
        Args:
            categorized: 分类后的证书信息
            
        Returns:
            bool: 通知是否发送成功
        """
        notification_sent = False
        
        # 检查是否需要发送通知
        if not (categorized['expired'] or categorized['expiring_soon']):
            self.logger_service.logger.info("所有证书状态正常，无需发送通知")
            return True
        
        notification_domains = categorized['expired'] + categorized['expiring_soon']
        
        try:
            # 如果域名数量很多，使用批量发送
            if len(notification_domains) > 20:
                self.logger_service.logger.info(f"域名数量较多({len(notification_domains)})，使用批量发送")
                notification_sent = self.notification_service.send_batch_notifications(notification_domains)
            else:
                notification_sent = self.notification_service.send_expiry_notification(notification_domains)
            
            self.logger_service.log_notification_sent("SNS", len(notification_domains), notification_sent)
            
        except Exception as e:
            self.logger_service.logger.error(f"发送通知时发生错误: {str(e)}")
            notification_sent = False
            
            # 尝试发送简化的错误通知
            try:
                self._send_error_notification(e, len(notification_domains))
            except Exception as fallback_error:
                self.logger_service.logger.error(f"发送错误通知也失败了: {str(fallback_error)}")
        
        return notification_sent
    
    def _send_status_report(self, all_certificates: List[CertificateInfo]) -> bool:
        """
        发送完整的SSL证书状态报告
        
        Args:
            all_certificates: 所有证书检查结果
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 获取执行摘要
            execution_summary = self.logger_service.get_execution_summary()
            
            # 发送状态报告
            success = self.notification_service.send_status_report(all_certificates, execution_summary)
            
            if success:
                self.logger_service.logger.info("SSL证书状态报告发送成功")
            else:
                self.logger_service.logger.error("SSL证书状态报告发送失败")
                
            return success
            
        except Exception as e:
            self.logger_service.logger.error(f"发送SSL证书状态报告时发生错误: {str(e)}")
            return False
    
    def _send_error_notification(self, error: Exception, domain_count: int):
        """
        发送错误通知
        
        Args:
            error: 发生的错误
            domain_count: 受影响的域名数量
        """
        error_message = (
            f"SSL证书监控系统通知发送失败\n\n"
            f"错误信息: {str(error)}\n"
            f"受影响域名数量: {domain_count}\n"
            f"时间: {datetime.now(timezone.utc).isoformat()}\n\n"
            f"请检查系统配置和网络连接。"
        )
        
        # 尝试发送简化的错误通知
        try:
            response = self.notification_service.sns_client.publish(
                TopicArn=self.notification_service.topic_arn,
                Subject="🚨 SSL证书监控系统错误",
                Message=error_message
            )
            self.logger_service.logger.info(f"错误通知发送成功，MessageId: {response.get('MessageId')}")
        except Exception as e:
            self.logger_service.logger.error(f"错误通知发送失败: {str(e)}")
    
    def validate_system_health(self) -> dict:
        """
        验证系统健康状态
        
        Returns:
            dict: 系统健康状态信息
        """
        health_status = {
            'overall_healthy': True,
            'components': {},
            'issues': []
        }
        
        try:
            # 检查域名配置
            domain_config = self.domain_manager.validate_configuration()
            health_status['components']['domain_config'] = {
                'healthy': domain_config['total_domains'] > 0,
                'details': domain_config
            }
            
            if domain_config['total_domains'] == 0:
                health_status['issues'].append("没有配置要监控的域名")
                health_status['overall_healthy'] = False
            
            # 检查SNS配置
            sns_config = self.notification_service.get_configuration_status()
            health_status['components']['sns_notification'] = {
                'healthy': sns_config['configuration_valid'],
                'details': sns_config
            }
            
            if not sns_config['configuration_valid']:
                health_status['issues'].append("SNS通知配置无效")
                health_status['overall_healthy'] = False
            
            # 测试SNS连接
            if sns_config['configuration_valid']:
                sns_connection = self.notification_service.test_connection()
                health_status['components']['sns_connection'] = {
                    'healthy': sns_connection,
                    'details': {'connection_test': sns_connection}
                }
                
                if not sns_connection:
                    health_status['issues'].append("SNS连接测试失败")
                    health_status['overall_healthy'] = False
            
        except Exception as e:
            health_status['overall_healthy'] = False
            health_status['issues'].append(f"健康检查时发生错误: {str(e)}")
        
        return health_status


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda函数入口点
    
    Args:
        event: EventBridge触发事件
        context: Lambda运行时上下文
        
    Returns:
        dict: 执行结果和统计信息
    """
    try:
        # 创建监控器实例
        monitor = SSLCertificateMonitor()
        
        # 执行检查
        result = monitor.execute()
        
        # 构建响应
        response = {
            'statusCode': 200,
            'body': {
                'message': 'SSL Certificate Monitor executed successfully',
                'summary': {
                    'total_domains': result.total_domains,
                    'successful_checks': result.successful_checks,
                    'failed_checks': result.failed_checks,
                    'expired_certificates': len(result.expired_domains),
                    'expiring_certificates': len(result.expiring_domains),
                    'execution_time_seconds': result.execution_time,
                    'success_rate': (
                        result.successful_checks / result.total_domains 
                        if result.total_domains > 0 else 0
                    )
                },
                'expired_domains': [cert.domain for cert in result.expired_domains],
                'expiring_domains': [cert.domain for cert in result.expiring_domains],
                'errors': result.errors[:5],  # 只返回前5个错误
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }
        
        # 如果有严重错误，返回错误状态码
        if result.total_domains == 0 and result.errors:
            response['statusCode'] = 500
            response['body']['message'] = 'SSL Certificate Monitor failed to execute'
        
        return response
        
    except Exception as e:
        # 处理未捕获的异常
        error_response = {
            'statusCode': 500,
            'body': {
                'message': 'SSL Certificate Monitor encountered a critical error',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        }
        
        # 尝试记录错误（如果可能）
        try:
            logger_service = LoggerService()
            logger_service.logger.error(f"Lambda函数执行时发生严重错误: {str(e)}")
        except:
            pass  # 如果连日志都无法记录，就忽略
        
        return error_response