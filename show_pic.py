import tkinter as tk
import os
import random
from PIL import Image, ImageTk

def create_pic_window():
    # 创建窗口
    window = tk.Tk()
    window.title("图片展示")

    # 获取屏幕分辨率
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    imgPath=''

    context_menu = tk.Menu(window, tearoff=0)
    window.bind("<Button-3>", lambda event: context_menu.post(event.x_root, event.y_root))

    # 幻灯片功能标志
    is_slideshow = False
    
    # 随机开关
    is_random = False

    # 显示图片数量
    images_per_view = 3

    #上一图片索引
    previous_image_index = 0

    # 幻灯片功能
    def toggle_slideshow():
        nonlocal is_slideshow
        is_slideshow = not is_slideshow
        if is_slideshow:
            start_slideshow()
        else:
            stop_slideshow()

    # 切换随机功能
    def toggle_random():
        nonlocal is_random
        is_random = not is_random
        if is_random:
            tk.messagebox.showinfo("随机开关","打开随机开关" )
        else:
            tk.messagebox.showinfo("随机开关","关闭随机开关" )

    def start_slideshow():
        show_next_images()
        if is_slideshow:
            window.after(3000, start_slideshow)

    def stop_slideshow():
        nonlocal is_slideshow
        is_slideshow = False

    # 切换显示图片数量
    def toggle_images_per_view():
        nonlocal images_per_view
        if images_per_view == 1:
            images_per_view = 2
            window.attributes('-fullscreen', True)
        else:
            images_per_view = 1
            window.attributes('-fullscreen', False)
            window.state('normal')
            window.update_idletasks()  # 更新窗口大小
            window.geometry(f"+{screen_width - window.winfo_width()}+0")
        update_images()

    # 添加随机开关菜单项
    context_menu.add_command(label="随机开关", command=toggle_random)
    # 添加幻灯片菜单项
    context_menu.add_command(label="幻灯片", command=toggle_slideshow)
    # 添加切换显示图片数量菜单项
    context_menu.add_command(label="切换显示数量", command=toggle_images_per_view)
    
    # 添加鼠标滚轮功能
    def on_mousewheel(event):
        if event.delta > 0:
            show_previous_images()  # 前滚显示上一页
        else:
            show_next_images()  # 后滚显示下一页
    
    window.bind("<MouseWheel>", on_mousewheel)
    
    # 导入剪贴板模块
    import pyperclip

    def set_imagePath(path):
        nonlocal imgPath
        imgPath=path

    # 添加复制图片信息菜单项
    def delete_image(img_path):
        if tk.messagebox.askyesno("确认删除", f"您确定要删除图片 '{os.path.basename(img_path)}' 吗？"):
            try:
                os.remove(img_path)
                images.remove(img_path)
                update_images()
            except Exception as e:
                tk.messagebox.showerror("删除失败", f"无法删除图片: {e}")

    def show_image_info(img_path):
        info = img_path.replace('/', '\\')
        tk.messagebox.showinfo("图片信息", info)
        pyperclip.copy(info)

    def move_to_best_folder(img_path):
        parent_dir = os.path.dirname(img_path)
        best_folder = os.path.join(parent_dir, "_精华")
        if not os.path.exists(best_folder):
            os.makedirs(best_folder)
        new_path = os.path.join(best_folder, os.path.basename(img_path))
        os.rename(img_path, new_path)
        images.remove(img_path)
        images.append(new_path)
        update_images()
        tk.messagebox.showinfo("移动成功", f"图片已移动到精华目录：{new_path}")

    context_menu.add_command(label="移到精华目录", command=lambda: move_to_best_folder(imgPath))
    context_menu.add_command(label="显示图片信息", command=lambda: show_image_info(imgPath))
    context_menu.add_command(label="删除图片", command=lambda: delete_image(imgPath))

    # 创建三个标签来显示图片
    frame = tk.Frame(window)
    frame.pack(fill=tk.BOTH, expand=True)

    labels = []
    for i in range(3):
        label = tk.Label(frame, width=int(screen_width/3), height=screen_height)
        label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        labels.append(label)

    # 存储图片引用以防被垃圾回收
    photos = [None, None, None]

    # 获取图片列表
    from tkinter import filedialog
    
    # 弹出对话框让用户选择目录
    image_dir = filedialog.askdirectory(title="请选择图片目录")
    if not image_dir:
        print("未选择目录。")
        window.destroy()
        return
    supported_formats = (".png", ".jpg", ".jpeg", ".gif", ".bmp")
    images = [os.path.join(image_dir, f) for f in os.listdir(image_dir) if f.lower().endswith(supported_formats)]
    images.sort(key=lambda x: os.path.getmtime(x), reverse=True)

    if not images:
        print("没有找到图片。")
        window.destroy()
        return

    current_image_index = 0
    previous_image_index = 0

    def show_next_images():
        nonlocal current_image_index
        nonlocal previous_image_index
        previous_image_index = current_image_index
        if is_random:
            current_image_index += random.randint(0,len(images)-1)
            if current_image_index >= len(images):
                current_image_index-=len(images)            
        if current_image_index + images_per_view < len(images):
            current_image_index += images_per_view
        else:
            current_image_index = 0
        update_images()

    def show_previous_images():
        nonlocal current_image_index
        nonlocal previous_image_index
        if current_image_index == previous_image_index:
            if current_image_index - images_per_view >= 0:
                current_image_index -= images_per_view
            else:
                current_image_index = max(0, len(images) - images_per_view)
            previous_image_index = current_image_index
        else:
            current_image_index = previous_image_index
        update_images()

    def update_images():
        nonlocal current_image_index
        for i in range(3):
            if i < images_per_view and current_image_index + i < len(images):
                img_path = images[current_image_index + i]
                try:
                    # 使用 PIL 库进行精确缩放
                    pil_image = Image.open(img_path)
                    original_width, original_height = pil_image.size

                    # 目标尺寸
                    target_width = int(screen_width / images_per_view)
                    target_height = screen_height

                    # 计算缩放比例
                    scale = max(original_width / target_width, original_height / target_height)

                    # 计算新的尺寸
                    new_width = int(original_width / scale)
                    new_height = int(original_height / scale)

                    resized_image = pil_image.resize((new_width, new_height), Image.LANCZOS)
                    photos[i] = ImageTk.PhotoImage(resized_image)

                    labels[i].config(image=photos[i])
                    labels[i].pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                    labels[i].bind("<Button-1>", lambda e: show_next_images())
                    labels[i].bind("<Button-2>", lambda e, path=img_path: delete_image(path))
                    labels[i].bind("<Double-Button-3>", lambda e, path=img_path: delete_image(path))
                    labels[i].bind("<Button-3>", lambda e, path=img_path: set_imagePath(path))

                except Exception as e:
                    print(f"无法加载图片 {img_path}: {e}")
            else:
                labels[i].pack_forget()
        
        # 更新窗口标题为第一张图片的文件名（不包含后缀）
        if current_image_index < len(images):
            file_name = os.path.splitext(os.path.basename(images[current_image_index]))[0]
            window.title(file_name)

    def toggle_fullscreen(event=None):
        window.attributes('-fullscreen', not window.attributes('-fullscreen'))
    def on_key_press(event):
        if event.keysym == "Return":
            toggle_fullscreen()
        elif event.keysym == "Escape":
            window.destroy()  # 退出应用
        elif event.keysym in ["Next", "Down", "Right", "space"]: 
            if is_slideshow:
                stop_slideshow()
            else:
                show_next_images()
        elif event.keysym in ["Prior", "Up", "Left"]:
            if is_slideshow:
                stop_slideshow()
            else:
                show_previous_images()


    window.bind("<KeyPress>", on_key_press)  # 绑定按键事件

    # 显示第一组图片
    update_images()
    window.state('iconic')
    window.state('zoomed')  # 窗口最大化
    window.mainloop()

create_pic_window()
