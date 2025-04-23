import os
import sys

def extract_chinese(text):
    chinese_chars = [char for char in text if '\u4e00' <= char <= '\u9fa5']
    chinese_text = ''.join(chinese_chars)
    return chinese_text

def arrange_pictures(pic_dir):
    if not os.path.exists(pic_dir):
        print(f"目录不存在: {pic_dir}")
        return False
        
    for filename in os.listdir(pic_dir):
        fileExt = filename.split(".")[-1].lower()
        if fileExt in ["png", "jpg", "jpeg"]:
            userName = extract_chinese(filename)
            if not userName:  # 如果没有提取到中文名字，跳过该文件
                continue
                
            userDir = os.path.join(pic_dir, userName)
            sorceFile = os.path.join(pic_dir, filename)
            destFile = os.path.join(pic_dir, userName, filename)
            
            if not os.path.exists(userDir):
                os.makedirs(userDir)
            if not os.path.exists(destFile):
                os.rename(sorceFile, destFile)
    return True

def main():
    if len(sys.argv) < 2:
        print("使用方法: python arrange_pic.py <目录1> [目录2] [目录3] ...")
        print("示例: python arrange_pic.py out images temp")
        sys.exit(1)
    
    success_count = 0
    for pic_dir in sys.argv[1:]:
        print(f"正在处理目录: {pic_dir}")
        if arrange_pictures(pic_dir):
            success_count += 1
            
    print(f"处理完成! 成功处理 {success_count} 个目录，共 {len(sys.argv)-1} 个目录")

if __name__ == "__main__":
    main()