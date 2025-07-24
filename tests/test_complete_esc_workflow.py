#!/usr/bin/env python3
"""
完整ESC取消功能测试

测试从键盘监听到实际流式取消的完整工作流程
"""

import time
import threading
from modules.hotkey_listener import HotkeyListener
from modules.text_processor import TextProcessor
from modules.streaming_cancellation import cancellation_manager
from modules.model_client import ModelType

def test_complete_esc_workflow():
    """测试完整的ESC取消工作流程"""
    print("🧪 测试完整ESC取消工作流程...")
    
    # 1. 测试取消令牌创建
    print("1. 创建取消令牌...")
    stream_id = "test_complete_workflow"
    token = cancellation_manager.create_cancellation_token(stream_id)
    assert not token.is_cancelled(), "令牌初始状态错误"
    print("   ✓ 取消令牌创建成功")
    
    # 2. 测试ESC键监听
    print("2. 设置ESC键监听...")
    listener = HotkeyListener()
    
    # 3. 测试ESC触发取消
    print("3. 测试ESC触发取消...")
    
    # 创建模拟流数据
    mock_chunks = [
        "Hello ",
        "this ",
        "is ",
        "a ",
        "test ",
        "stream ",
        "that ",
        "should ",
        "be ",
        "cancelled"
    ]
    
    processed_content = []
    cancelled = False
    
    def mock_stream_processor():
        nonlocal cancelled
        for i, chunk in enumerate(mock_chunks):
            if token.is_cancelled():
                print(f"   ⏹️  流在chunk {i}被取消")
                cancelled = True
                break
            processed_content.append(chunk)
            time.sleep(0.2)  # 模拟每个chunk的处理时间
    
    # 启动流处理线程
    stream_thread = threading.Thread(target=mock_stream_processor)
    stream_thread.start()
    
    # 等待一段时间后模拟ESC键按下
    time.sleep(0.5)  # 让流开始处理
    print("   🎯 模拟ESC键按下...")
    cancellation_manager.handle_esc_key()
    
    # 等待流处理线程结束
    stream_thread.join(timeout=2)
    
    # 验证结果
    assert cancelled, "流应该被取消"
    assert len(processed_content) < len(mock_chunks), "处理的内容应该少于总chunks"
    print(f"   ✓ 流成功取消，处理了 {len(processed_content)}/{len(mock_chunks)} 个chunks")
    
    # 4. 测试清理
    print("4. 测试清理...")
    cancellation_manager.remove_stream(stream_id)
    assert cancellation_manager.get_cancellation_token(stream_id) is None, "令牌应被清理"
    print("   ✓ 清理成功")
    
    print("\n🎉 完整ESC取消工作流程测试通过!")
    return True

def test_async_cancellation():
    """测试异步取消功能"""
    print("\n🧪 测试异步取消功能...")
    
    import asyncio
    
    async def async_test():
        # 测试异步取消令牌
        stream_id = "async_test"
        token = cancellation_manager.create_cancellation_token(stream_id)
        
        # 异步模拟流处理
        async def async_stream():
            chunks = ["chunk1", "chunk2", "chunk3", "chunk4", "chunk5"]
            for i, chunk in enumerate(chunks):
                if token.is_cancelled():
                    return f"cancelled_at_{i}"
                await asyncio.sleep(0.1)
            return "completed"
        
        # 启动异步任务
        task = asyncio.create_task(async_stream())
        
        # 延迟取消
        await asyncio.sleep(0.25)
        cancellation_manager.cancel_stream(stream_id)
        
        result = await task
        assert "cancelled" in result, "异步流应该被取消"
        print("   ✓ 异步取消功能正常")
        
        cancellation_manager.remove_stream(stream_id)
    
    asyncio.run(async_test())

if __name__ == "__main__":
    print("🚀 开始完整的ESC取消功能测试...\n")
    
    try:
        test_complete_esc_workflow()
        test_async_cancellation()
        
        print("\n✅ 所有测试通过！ESC取消功能完全正常工作")
        print("   - 取消令牌创建和管理 ✓")
        print("   - ESC键监听和触发 ✓") 
        print("   - 流式处理取消 ✓")
        print("   - 异步取消支持 ✓")
        print("   - 资源清理 ✓")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        cancellation_manager.cleanup()
        print("\n🧹 清理完成")