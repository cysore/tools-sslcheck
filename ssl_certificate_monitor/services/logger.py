"""
日志服务
"""
import os
import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from ..interfaces import LoggerServiceInterface
from ..models import CertificateInfo


class LoggerService(LoggerServiceInterface):
    """日志服务实现"""
    
    def __init__(self, logger_name: str = "ssl_certificate_monitor", log_level: Optional[str] = None):
        """
        初始化日志服务
        
        Args:
            logger_name: 日志器名称
            log_level: 日志级别，如果为None则从环境变量读取
        """
        self.logger_name = logger_name
        self.log_level = log_level or os.getenv('LOG_LEVEL', 'INFO')
        
        # 配置日志器
        self.logger = logging.getLogger(logger_name)
        self._configure_logger()
        
        # 执行统计
        self.execution_stats = {
            'start_time': None,
            'end_time': None,
            'total_domains': 0,
            'successful_checks': 0,
            'failed_checks': 0,
            'errors': []
        }
    
    def _configure_logger(self):
        """配置日志器"""
        # 设置日志级别
        level = getattr(logging, self.log_level.upper(), logging.INFO)
        self.logger.setLevel(level)
        
        # 避免重复添加处理器
        if not self.logger.handlers:
            # 创建控制台处理器
            handler = logging.StreamHandler()
            handler.setLevel(level)
            
            # 创建格式化器
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            
            self.logger.addHandler(handler)
        
        # 防止日志传播到根日志器
        self.logger.propagate = False
    
    def log_check_start(self, domain_count: int):
        """
        记录检查开始
        
        Args:
            domain_count: 要检查的域名数量
        """
        self.execution_stats['start_time'] = datetime.now(timezone.utc)
        self.execution_stats['total_domains'] = domain_count
        
        self.logger.info(f"开始SSL证书检查，共 {domain_count} 个域名")
        self.logger.info(f"检查开始时间: {self.execution_stats['start_time'].isoformat()}")
    
    def log_certificate_info(self, domain: str, cert_info: CertificateInfo):
        """
        记录证书信息
        
        Args:
            domain: 域名
            cert_info: 证书信息
        """
        if cert_info.is_valid:
            self.execution_stats['successful_checks'] += 1
            
            if cert_info.is_expired:
                self.logger.warning(
                    f"证书已过期 - 域名: {domain}, "
                    f"过期时间: {cert_info.expiry_date.isoformat()}, "
                    f"已过期: {abs(cert_info.days_until_expiry)} 天, "
                    f"颁发者: {cert_info.issuer}"
                )
            elif cert_info.is_expiring_soon:
                self.logger.warning(
                    f"证书即将过期 - 域名: {domain}, "
                    f"过期时间: {cert_info.expiry_date.isoformat()}, "
                    f"剩余天数: {cert_info.days_until_expiry} 天, "
                    f"颁发者: {cert_info.issuer}"
                )
            else:
                self.logger.info(
                    f"证书正常 - 域名: {domain}, "
                    f"过期时间: {cert_info.expiry_date.isoformat()}, "
                    f"剩余天数: {cert_info.days_until_expiry} 天, "
                    f"颁发者: {cert_info.issuer}"
                )
        else:
            self.execution_stats['failed_checks'] += 1
            self.logger.error(
                f"证书检查失败 - 域名: {domain}, "
                f"错误: {cert_info.error_message}"
            )
    
    def log_error(self, domain: str, error: Exception):
        """
        记录错误信息
        
        Args:
            domain: 域名
            error: 异常对象
        """
        error_info = {
            'domain': domain,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        self.execution_stats['errors'].append(error_info)
        
        self.logger.error(
            f"域名 {domain} 检查时发生错误: {type(error).__name__}: {str(error)}"
        )
        
        # 记录详细的堆栈跟踪（调试级别）
        self.logger.debug(f"域名 {domain} 错误堆栈跟踪:\n{traceback.format_exc()}")
    
    def log_check_end(self):
        """记录检查结束"""
        self.execution_stats['end_time'] = datetime.now(timezone.utc)
        
        if self.execution_stats['start_time']:
            duration = (self.execution_stats['end_time'] - self.execution_stats['start_time']).total_seconds()
        else:
            duration = 0
        
        self.logger.info(f"SSL证书检查完成")
        self.logger.info(f"检查结束时间: {self.execution_stats['end_time'].isoformat()}")
        self.logger.info(f"总执行时间: {duration:.2f} 秒")
        self.logger.info(
            f"检查统计: 总计 {self.execution_stats['total_domains']} 个域名, "
            f"成功 {self.execution_stats['successful_checks']} 个, "
            f"失败 {self.execution_stats['failed_checks']} 个"
        )
    
    def log_notification_sent(self, notification_type: str, recipient_count: int, success: bool):
        """
        记录通知发送状态
        
        Args:
            notification_type: 通知类型（如 "SNS"）
            recipient_count: 接收者数量
            success: 是否发送成功
        """
        if success:
            self.logger.info(
                f"{notification_type} 通知发送成功，接收者数量: {recipient_count}"
            )
        else:
            self.logger.error(
                f"{notification_type} 通知发送失败，接收者数量: {recipient_count}"
            )
    
    def log_configuration_info(self, config: Dict[str, Any]):
        """
        记录配置信息
        
        Args:
            config: 配置信息字典
        """
        # 过滤敏感信息
        safe_config = self._sanitize_config(config)
        
        self.logger.info("系统配置信息:")
        for key, value in safe_config.items():
            self.logger.info(f"  {key}: {value}")
    
    def _sanitize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理配置信息中的敏感数据
        
        Args:
            config: 原始配置
            
        Returns:
            Dict[str, Any]: 清理后的配置
        """
        sensitive_keys = {
            'password', 'secret', 'token', 'credential', 'sns_topic_arn'
        }
        
        # 包含敏感词的键名
        sensitive_patterns = {'password', 'secret', 'token', 'credential'}
        
        safe_config = {}
        for key, value in config.items():
            key_lower = key.lower()
            
            # 检查是否是敏感键名
            is_sensitive = (
                key_lower in sensitive_keys or
                key_lower == 'password' or
                key_lower == 'secret' or
                key_lower == 'token' or
                key_lower == 'key' or
                key_lower.endswith('_key') or
                key_lower.endswith('_secret') or
                key_lower.endswith('_password') or
                key_lower.endswith('_token')
            )
            
            if is_sensitive and isinstance(value, str) and value:
                if 'arn:' in value:
                    # ARN类型，只显示前缀和后缀
                    parts = value.split(':')
                    if len(parts) >= 6:
                        safe_value = f"{':'.join(parts[:3])}:***:{parts[-2]}:{parts[-1]}"
                    else:
                        safe_value = "***"
                else:
                    # 其他敏感信息，只显示前几个字符
                    safe_value = value[:3] + "***" if len(value) > 3 else "***"
                safe_config[key] = safe_value
            else:
                safe_config[key] = value
        
        return safe_config
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        获取执行摘要
        
        Returns:
            Dict[str, Any]: 执行摘要信息
        """
        duration = 0
        if self.execution_stats['start_time'] and self.execution_stats['end_time']:
            duration = (self.execution_stats['end_time'] - self.execution_stats['start_time']).total_seconds()
        
        return {
            'start_time': self.execution_stats['start_time'].isoformat() if self.execution_stats['start_time'] else None,
            'end_time': self.execution_stats['end_time'].isoformat() if self.execution_stats['end_time'] else None,
            'duration_seconds': duration,
            'total_domains': self.execution_stats['total_domains'],
            'successful_checks': self.execution_stats['successful_checks'],
            'failed_checks': self.execution_stats['failed_checks'],
            'success_rate': (
                self.execution_stats['successful_checks'] / self.execution_stats['total_domains']
                if self.execution_stats['total_domains'] > 0 else 0
            ),
            'error_count': len(self.execution_stats['errors']),
            'errors': self.execution_stats['errors']
        }
    
    def log_execution_summary(self):
        """记录执行摘要"""
        summary = self.get_execution_summary()
        
        self.logger.info("=" * 50)
        self.logger.info("执行摘要")
        self.logger.info("=" * 50)
        
        if summary['start_time']:
            self.logger.info(f"开始时间: {summary['start_time']}")
        if summary['end_time']:
            self.logger.info(f"结束时间: {summary['end_time']}")
        
        self.logger.info(f"执行时长: {summary['duration_seconds']:.2f} 秒")
        self.logger.info(f"总域名数: {summary['total_domains']}")
        self.logger.info(f"成功检查: {summary['successful_checks']}")
        self.logger.info(f"失败检查: {summary['failed_checks']}")
        self.logger.info(f"成功率: {summary['success_rate']:.1%}")
        
        if summary['errors']:
            self.logger.info(f"错误数量: {summary['error_count']}")
            for i, error in enumerate(summary['errors'][:5], 1):  # 只显示前5个错误
                self.logger.info(f"  错误 {i}: {error['domain']} - {error['error_type']}: {error['error_message']}")
            
            if len(summary['errors']) > 5:
                self.logger.info(f"  ... 还有 {len(summary['errors']) - 5} 个错误")
        
        self.logger.info("=" * 50)
    
    def reset_stats(self):
        """重置执行统计"""
        self.execution_stats = {
            'start_time': None,
            'end_time': None,
            'total_domains': 0,
            'successful_checks': 0,
            'failed_checks': 0,
            'errors': []
        }