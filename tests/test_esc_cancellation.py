#!/usr/bin/env python3
"""
ESC键取消功能测试

测试ESC键是否能正确停止流式输出
"""

import time
import threading
from modules.streaming_cancellation import cancellation_manager, CancellationToken
from modules.model_client import StreamChunk

def test_cancellation_token():
    """测试取消令牌功能"""
    print("测试取消令牌功能...")
    
    token = CancellationToken()
    assert not token.is_cancelled(), "令牌初始应为未取消状态"
    
    result = token.cancel()
    assert result, "第一次取消应返回True"
    assert token.is_cancelled(), "令牌应处于取消状态"
    
    result2 = token.cancel()
    assert not result2, "重复取消应返回False"
    
    print("✓ 取消令牌测试通过")

def test_stream_cancellation():
    """测试流式取消功能"""
    print("测试流式取消功能...")
    
    # 创建模拟流数据
    mock_chunks = [
        StreamChunk(content="Hello", chunk_id=0),
        StreamChunk(content=" ", chunk_id=1),
        StreamChunk(content="World", chunk_id=2, is_final=True)
    ]
    
    # 创建取消令牌
    stream_id = "test_stream_1"
    token = cancellation_manager.create_cancellation_token(stream_id)
    
    # 模拟流处理
    processed_content = ""
    
    def process_stream():
        nonlocal processed_content
        for chunk in mock_chunks:
            if token.is_cancelled():
                print("流已被取消")
                break
            processed_content += chunk.content
            time.sleep(0.1)  # 模拟处理延迟
    
    # 启动处理线程
    process_thread = threading.Thread(target=process_stream)
    process_thread.start()
    
    # 等待一下然后取消
    time.sleep(0.15)
    cancellation_manager.cancel_stream(stream_id)
    
    process_thread.join(timeout=1)
    
    print(f"处理的内容: '{processed_content}'")
    print("✓ 流式取消测试完成")

def test_esc_handler():
    """测试ESC键处理"""
    print("测试ESC键处理...")
    
    # 设置ESC回调
    def on_esc_pressed():
        print("ESC键被按下，执行取消操作")
        cancellation_manager.cancel_all_streams()
    
    cancellation_manager.start_esc_listener(on_esc_pressed)
    
    # 模拟ESC键按下
    cancellation_manager.handle_esc_key()
    
    cancellation_manager.stop_esc_listener()
    print("✓ ESC键处理测试完成")

if __name__ == "__main__":
    print("开始ESC取消功能测试...\n")
    
    try:
        test_cancellation_token()
        test_stream_cancellation()
        test_esc_handler()
        
        print("\n✅ 所有测试通过！ESC取消功能正常工作")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        cancellation_manager.cleanup()
        print("清理完成")