import os

pic_dir="out"
path=os.path.dirname(os.path.realpath(__file__))


#函数：提取字符串中的中文
def extract_chinese(text):
    chinese_chars = [char for char in text if '\u4e00' <= char <= '\u9fa5']
    chinese_text = ''.join(chinese_chars)
    return chinese_text

for filename in os.listdir(pic_dir):
    fileExt=filename.split(".")[-1]
    if  fileExt == "png" or fileExt == "jpg" or fileExt == "jpeg":
        userName=extract_chinese(filename)
        userDir=pic_dir+'/'+userName
        sorceFile=pic_dir+'/'+filename
        destFile=pic_dir+'/'+userName+'/'+filename
        if not os.path.exists(userDir):
            os.makedirs(userDir)
        if not os.path.exists(destFile):
            os.rename(sorceFile,destFile)

print ("all done!")