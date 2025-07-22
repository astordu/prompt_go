#!/usr/bin/env python3
"""
配置文件动态重新加载功能演示脚本

运行此脚本可以演示配置文件变化时的自动重新加载功能
使用方法: python tests/test_config_reload_demo.py
"""

import time
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.config_manager import GlobalConfigManager, HotkeyConfigManager


def demo_global_config_reload():
    """演示全局配置的动态重新加载"""
    print("🔧 演示全局配置动态重新加载...")
    
    config_manager = GlobalConfigManager()
    config_manager.load_config()
    
    # 启动文件监控
    config_manager.start_watching()
    
    print(f"📋 当前日志级别: {config_manager.get('logging.level')}")
    print(f"📋 当前超时时间: {config_manager.get('performance.response_timeout')}秒")
    
    print("\n💡 程序正在监控配置文件变化...")
    print("💡 请在另一个终端修改 config/global_config.yaml 文件")
    print("💡 例如：将 logging.level 从 INFO 改为 DEBUG")
    print("💡 或者将 response_timeout 改为其他值")
    print("💡 按 Ctrl+C 退出演示\n")
    
    try:
        while True:
            current_level = config_manager.get('logging.level')
            current_timeout = config_manager.get('performance.response_timeout')
            
            print(f"⏰ {time.strftime('%H:%M:%S')} - 日志级别: {current_level}, 超时: {current_timeout}秒")
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\n🛑 停止配置监控...")
        config_manager.stop_watching()
        print("✅ 演示完成")


def demo_hotkey_config_reload():
    """演示快捷键配置的动态重新加载"""
    print("⌨️ 演示快捷键配置动态重新加载...")
    
    hotkey_manager = HotkeyConfigManager()
    hotkey_manager.load_config()
    
    # 启动文件监控
    hotkey_manager.start_watching()
    
    print(f"📋 当前快捷键状态: {'启用' if hotkey_manager.get('settings.enabled') else '禁用'}")
    print(f"📋 当前响应延迟: {hotkey_manager.get('settings.response_delay')}ms")
    
    # 显示前3个快捷键映射
    mappings = hotkey_manager.get_all_mappings()
    print("📋 前3个快捷键映射:")
    for hotkey, template in list(mappings.items())[:3]:
        print(f"   {hotkey} -> {template}")
    
    print("\n💡 程序正在监控配置文件变化...")
    print("💡 请在另一个终端修改 config/hotkey_mapping.yaml 文件")
    print("💡 例如：将某个模板名改为其他名称")
    print("💡 或者修改 settings.response_delay 的值")
    print("💡 按 Ctrl+C 退出演示\n")
    
    try:
        while True:
            enabled = hotkey_manager.get('settings.enabled')
            delay = hotkey_manager.get('settings.response_delay')
            current_mappings = hotkey_manager.get_all_mappings()
            
            print(f"⏰ {time.strftime('%H:%M:%S')} - 启用: {enabled}, 延迟: {delay}ms, 映射数: {len(current_mappings)}")
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\n🛑 停止配置监控...")
        hotkey_manager.stop_watching()
        print("✅ 演示完成")


def run_automated_test():
    """运行自动化测试验证功能"""
    print("🤖 运行自动化测试...")
    
    # 测试全局配置自动重新加载
    print("\n📋 测试全局配置自动重新加载")
    config_manager = GlobalConfigManager()
    config_manager.load_config()
    config_manager.start_watching()
    
    initial_timeout = config_manager.get('performance.response_timeout')
    print(f"初始超时时间: {initial_timeout}秒")
    
    # 修改配置
    config_data = config_manager.config_data.copy()
    test_timeout = 45
    config_data['performance']['response_timeout'] = test_timeout
    config_manager.save_config(config_data)
    
    # 等待自动重新加载
    time.sleep(1)
    
    new_timeout = config_manager.get('performance.response_timeout')
    print(f"修改后超时时间: {new_timeout}秒")
    
    if new_timeout == test_timeout:
        print("✅ 全局配置自动重新加载测试通过")
    else:
        print("❌ 全局配置自动重新加载测试失败")
    
    # 恢复原始配置
    config_data['performance']['response_timeout'] = initial_timeout
    config_manager.save_config(config_data)
    config_manager.stop_watching()
    
    # 测试快捷键配置自动重新加载
    print("\n📋 测试快捷键配置自动重新加载")
    hotkey_manager = HotkeyConfigManager()
    hotkey_manager.load_config()
    hotkey_manager.start_watching()
    
    initial_delay = hotkey_manager.get('settings.response_delay')
    print(f"初始响应延迟: {initial_delay}ms")
    
    # 修改配置
    hotkey_data = hotkey_manager.config_data.copy()
    test_delay = 150
    hotkey_data['settings']['response_delay'] = test_delay
    hotkey_manager.save_config(hotkey_data)
    
    # 等待自动重新加载
    time.sleep(1)
    
    new_delay = hotkey_manager.get('settings.response_delay')
    print(f"修改后响应延迟: {new_delay}ms")
    
    if new_delay == test_delay:
        print("✅ 快捷键配置自动重新加载测试通过")
    else:
        print("❌ 快捷键配置自动重新加载测试失败")
    
    # 恢复原始配置
    hotkey_data['settings']['response_delay'] = initial_delay
    hotkey_manager.save_config(hotkey_data)
    hotkey_manager.stop_watching()
    
    print("\n✅ 所有自动化测试完成")


def main():
    """主函数"""
    print("=" * 60)
    print("📝 配置文件动态重新加载功能演示")
    print("=" * 60)
    
    choice = input("""
选择演示模式:
1. 全局配置重新加载演示 (需要手动修改配置文件)
2. 快捷键配置重新加载演示 (需要手动修改配置文件)
3. 运行自动化测试

请输入 (1/2/3): """).strip()
    
    if choice == "1":
        demo_global_config_reload()
    elif choice == "2":
        demo_hotkey_config_reload()
    elif choice == "3":
        run_automated_test()
    else:
        print("❌ 无效选择")
        return


if __name__ == "__main__":
    main() 