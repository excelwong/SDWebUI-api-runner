import os
import shutil

def process_requirements_files(root_dir):
    for root, dirs, files in os.walk(root_dir):
        # 检查当前目录中是否有requirements.txt
        if 'requirements.txt' in files:
            txt_path = os.path.join(root, 'requirements.txt')
            bak_path = os.path.join(root, 'requirements.bak')
            
            # 检查文件大小
            if os.path.getsize(txt_path) > 0:
                # 如果.bak文件已存在，先删除
                if os.path.exists(bak_path):
                    os.remove(bak_path)
                    print(f"已删除旧备份文件: {bak_path}")
                
                # 重命名文件
                os.rename(txt_path, bak_path)
                print(f"已将 {txt_path} 重命名为 {bak_path}")
                
                # 创建新的空requirements.txt
                with open(txt_path, 'w') as f:
                    pass  # 创建空文件
                print(f"已创建新的空文件: {txt_path}")
            else:
                print(f"跳过空文件: {txt_path}")

if __name__ == "__main__":
    target_dir = r"D:\ComfyUI-aki\custom_nodes"
    if os.path.exists(target_dir):
        process_requirements_files(target_dir)
        print("处理完成！")
    else:
        print(f"目录不存在: {target_dir}")