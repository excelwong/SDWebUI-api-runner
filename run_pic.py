import base64, io, os, requests, json
from PIL import Image, PngImagePlugin
import re,random
import gc,torch
import sys

resume_point=99999

#读取JSON格式的配置文件
def load_config(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

sys_config=load_config("sys_config.txt")
address=sys_config["address"]
out_dir=sys_config["out_dir"]
ref_dir=sys_config["ref_dir"]
user_dir=sys_config["user_dir"]
if not os.path.exists(out_dir):
    os.makedirs(out_dir)
if not os.path.exists(ref_dir) or not os.path.exists(user_dir):
    print("ref_dir or user_dir not exists.")
    exit()

#截断prompt，用来生成文件名
def trim_prompt(prompt:str):
    return prompt.replace(', ',',').replace('masterpiece,best quality,ultra highres,ultra-detailed,realistic,photorealistic,','').replace('simple background,white background,','').replace('1girl,solo,','').replace('looking_at_viewer,','')
#图像与Base64字符串互相转换
def image_to_base64(image: Image.Image, fmt='png') -> str:
    output_buffer = io.BytesIO()
    image.save(output_buffer, format=fmt)
    byte_data = output_buffer.getvalue()
    base64_str = base64.b64encode(byte_data).decode('utf-8')
    return f'data:image/{fmt};base64,' + base64_str
def base64_to_image(base64_str: str) -> Image.Image:
    img=Image.open(io.BytesIO(base64.b64decode(base64_str))).convert("RGB")
    return img
#读取prompt_config.txt和prompt_group.txt两个配置文件，生成正负提示词
def generate_prompts(prompt_config, prompt_groups):
    selected_items = {}

    # 处理服装组逻辑
    if prompt_config.get("服装", 0) > 0:
        prompt_config["上装"] = 0
        prompt_config["下装"] = 0

    # 处理颜色提示词（独立逻辑）
    color_value = prompt_config.get("颜色", -1)
    color_options = prompt_groups.get("颜色", [])
    if color_options:
        if color_value == -1:
            color_selected = random.choice(color_options)
        else:
            # 严格索引处理
            if 0 <= color_value < len(color_options):
                color_selected = color_options[color_value]
            else:
                color_selected = random.choice(color_options)
    else:
        color_selected = ""
    color_prompt = color_selected.strip()

    # 处理材质提示词（独立逻辑）
    material_value = prompt_config.get("材质", -1)
    material_options = prompt_groups.get("材质", [])
    if material_options:
        if material_value == -1:
            material_selected = random.choice(material_options)
        else:
            # 严格索引处理
            if 0 <= material_value < len(material_options):
                material_selected = material_options[material_value]
            else:
                material_selected = random.choice(material_options)
    else:
        material_selected = ""
    material_prompt = material_selected.strip()

    # 处理常规提示词组
    for group_name in prompt_config:
        if group_name == "负面提示词" or group_name == "颜色" or group_name == "材质":
            continue  # 单独处理负面提示词和颜色、材质

        value = prompt_config[group_name]
        options = prompt_groups.get(group_name, [])
        
        # 空选项组处理
        if not options:
            selected = ""
        else:
            # 选择逻辑
            if value == -1:
                selected = random.choice(options)
            else:
                # 处理索引越界
                selected = options[value] if 0 <= value < len(options) else random.choice(options)

        selected_items[group_name] = selected.strip()
        if (group_name=="服装" or group_name=="上装") and selected_items[group_name] !=options[0] and selected_items[group_name] !=options[1]: #服装或者上装不为空（0）不为裸（1），就加上颜色和材质
            if material_prompt!="": 
                selected_items[group_name] = f"{material_prompt}_{selected_items[group_name]}"
            if color_prompt!="":
                selected_items[group_name] = f"{color_prompt}_{selected_items[group_name]}"

    # 处理负面提示词（独立逻辑）
    neg_value = prompt_config.get("负面提示词", -1)
    neg_options = prompt_groups.get("负面提示词", [])
    if neg_options:
        if neg_value == -1:
            neg_selected = random.choice(neg_options)
        else:
            # 严格索引处理
            if 0 <= neg_value < len(neg_options):
                neg_selected = neg_options[neg_value]
            else:
                neg_selected = random.choice(neg_options)
    else:
        neg_selected = ""
    neg_prompt = neg_selected.strip()

    # 生成正面提示词
    if prompt_config.get("套装", 0) > 0:
        prompt = selected_items.get("套装", "")
    else:
        # 按配置键顺序组装（排除特定组）
        excluded = {"套装", "负面提示词","颜色", "材质"}
        prompt_parts = [v for k, v in selected_items.items() if k not in excluded and v]
        prompt = ",".join(prompt_parts)
    # 最终清理
    return prompt.strip(), neg_prompt.strip()
#根据参考图片名、用户图片名，生成新的图片名
def generate_filename(payload,image:Image.Image):
    prompt = trim_prompt(payload["prompt"])
    seed = payload["seed"]
    user_name = os.path.splitext(os.path.split(image.filename)[1])[0]
    return f"{user_name}-{prompt},{seed}.png"
#解析字符串为payload
def parse_txt_to_payload(text):
    # 第一阶段：分割 prompt 和 negative_prompt（保留末尾逗号）
    parts = text.split('\n', 2)
    prompt = parts[0].strip()  # 保留原始末尾逗号
    negative_prompt = parts[1].replace('Negative prompt: ', '', 1).strip()  # 保留原始末尾逗号
    remaining = parts[2] if len(parts) > 2 else ''

    # 第二阶段：处理 ControlNet 参数（过滤不需要的字段）
    quote_split = remaining.split('"')
    controlnet_args = []
    filtered_keys = {'processor_res', 'threshold_a', 'threshold_b', 'guidance_start', 'guidance_end'}
    
    for i in range(1, len(quote_split), 2):
        arg_dict = {}
        for pair in quote_split[i].split(','):
            pair = pair.strip()
            if not pair or ':' not in pair:
                continue
            key, val = pair.split(':', 1)
            key = key.strip().lower().replace(' ', '_')
            val = val.strip()
            
            # 过滤不需要的字段
            if key in filtered_keys:
                continue
                
            # 类型转换逻辑
            if key == 'weight':
                val = int(float(val))  # 1.0 -> 1
            elif key == 'pixel_perfect':
                val = val.lower() == 'true'
            elif key == 'control_mode':
                val = val.capitalize()
            
            arg_dict[key] = val
        
        # 添加 ControlNet 默认参数
        arg_dict.update({
            'enabled': True,
            'low_vram': False,
            'image': 'user_base64_str' if i == 1 else 'ref_base64_str'
        })
        controlnet_args.append(arg_dict)

    # 第三阶段：处理普通参数
    param_dict = {
        'override_settings': {'sd_model_checkpoint': ''},
        'enable_hr': False
    }
    
    # 合并普通参数部分
    normal_str = ''.join(quote_split[::2])
    for pair in normal_str.split(','):
        pair = pair.strip()
        if not pair or ':' not in pair:
            continue
        
        key, val = pair.split(':', 1)
        key = key.strip().lower().replace(' ', '_')
        val = val.strip()
        
        # 特殊字段处理
        if key == 'size':
            w, h = val.split('x')
            param_dict['width'] = int(w)
            param_dict['height'] = int(h)
        elif key == 'model':
            param_dict['override_settings']['sd_model_checkpoint'] = val
        # Hires 参数处理
        elif key == 'hires_upscale':
            param_dict['hr_scale'] = float(val)
        elif key == 'hires_steps':
            param_dict['hr_second_pass_steps'] = int(val)
        elif key == 'hires_upscaler':
            param_dict['hr_upscaler'] = val
        # 常规类型转换
        elif key in ['steps', 'seed', 'clip_skip']:
            param_dict[key] = int(val)
        elif key in ['cfg_scale', 'denoising_strength']:
            param_dict[key] = float(val)
        else:
            param_dict[key] = val

    # 构建最终 payload
    payload = {
        'prompt': prompt,
        'negative_prompt': negative_prompt,
        'seed': param_dict.get('seed', 0),
        'steps': param_dict.get('steps', 20),
        'cfg_scale': param_dict.get('cfg_scale', 7.0),
        'width': param_dict.get('width', 512),
        'height': param_dict.get('height', 768),
        'sampler_index': param_dict.get('sampler', ''),
        'scheduler': param_dict.get('schedule_type', ''),
        'override_settings': param_dict['override_settings'],
        'enable_hr': param_dict['enable_hr']
    }
    
    # 处理 payload2 特有参数
    if controlnet_args:
        payload.update({
            'alwayson_scripts': {
                'ControlNet': {'args': controlnet_args}
            },
            'denoising_strength': param_dict.get('denoising_strength', 0.75),
            'hr_scale': param_dict.get('hr_scale', 2.0),
            'hr_second_pass_steps': param_dict.get('hr_second_pass_steps', 0),
            'hr_upscaler': param_dict.get('hr_upscaler', ''),
            'enable_hr': True
        })
    
    return payload
#将ref_img图片按照sys_config的配置放大，脸换成user_img，生成payload
def generate_payload(ref_img:Image.Image,user_img:Image.Image):
    if(ref_img.format != 'PNG' or "parameters" not in ref_img.info):
        print("Reference image '"+ref_img.filename +"' was not generated by StableDiffusion WebUI!")
        return None

    user_base64_str=image_to_base64(user_img)
    ref_base64_str=image_to_base64(ref_img)
    # 构建 JSON 对象
    payload = parse_txt_to_payload(ref_img.text["parameters"])
    sys_config=load_config("sys_config.txt")
    payload.update({
        "alwayson_scripts": {
            "ControlNet": {
                "args": [
                    {
                        "image": user_base64_str,
                        "enabled": True,
                        "low_vram": False, 
                        "pixel_perfect": True, 
                        "module": "instant_id_face_embedding", 
                        "model": "ip-adapter_instant_id_sdxl [eb2d3ec0]", 
                        "weight": 1, 
                        "guidance_start": 0, 
                        "guidance_end": 1, 
                        "control_mode": "Balanced", 
                        "resize_mode": "Crop and Resize"
                    },
                    {
                        "image": ref_base64_str,
                        "enabled": True,
                        "low_vram": False,  
                        "pixel_perfect": True, 
                        "module": "instant_id_face_keypoints", 
                        "model": "control_instant_id_sdxl [c5c25a50]", 
                        "weight": 1, 
                        "guidance_start": 0, 
                        "guidance_end": 1, 
                        "control_mode": "Balanced", 
                        "resize_mode": "Crop and Resize"
                    }
                ]
            }
        },
        "denoising_strength": sys_config["denoising_strength"],
        "hr_scale": sys_config["hr_scale"],
        "hr_second_pass_steps": sys_config["hr_second_pass_steps"],
        "hr_upscaler": sys_config["hr_upscaler"],
        "enable_hr": True
        })
    return payload
#从payload和seed生成pngInfo
def parse_payload_to_pngInfo(payload,newSeed=-1):
    lines = []
    
    # 处理基础提示词
    prompt = payload.get("prompt", "")
    negative_prompt = payload.get("negative_prompt", "")
    if negative_prompt:
        prompt += f"\nNegative prompt: {negative_prompt.rstrip(',')}\n"

    # 基础参数
    base_params = []
    if steps := payload.get("steps"):
        base_params.append(f"Steps: {steps}")
    if sampler := payload.get("sampler_index"):
        base_params.append(f"Sampler: {sampler}")
    if scheduler := payload.get("scheduler"):
        base_params.append(f"Schedule type: {scheduler}")
    if cfg := payload.get("cfg_scale"):
        base_params.append(f"CFG scale: {cfg}")
    if seed := payload.get("seed"):
        if(seed==-1):seed=newSeed
        base_params.append(f"Seed: {seed}")
    if all(k in payload for k in ("width", "height")):
        base_params.append(f"Size: {payload['width']}x{payload['height']}")
    if base_params:
        lines.append(", ".join(base_params))

    # 模型信息
    model_hash = "9748eda16e"
    model = payload.get("override_settings", {}).get("sd_model_checkpoint", "")
    lines.append(f"Model hash: {model_hash}, Model: {model}")

    # 去噪强度
    if ds := payload.get("denoising_strength"):
        lines.append(f"Denoising strength: {ds}")

    # 固定参数
    lines.append("Clip skip: 2")

    # 处理ControlNet（固定内容）
    if cn := payload.get("alwayson_scripts", {}).get("ControlNet", {}).get("args", []):
        fixed_controls = [
            'Module: instant_id_face_embedding, Model: ip-adapter_instant_id_sdxl [eb2d3ec0], Weight: 1.0, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 0.5, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced',
            'Module: instant_id_face_keypoints, Model: control_instant_id_sdxl [c5c25a50], Weight: 1.0, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 0.5, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: False, Control Mode: Balanced'
        ]
        for i in range(len(cn)):
            if i < len(fixed_controls):
                lines.append(f'ControlNet {i}: "{fixed_controls[i]}"')

    # 处理高清修复
    if payload.get("enable_hr", False):
        hr_params = []
        if scale := payload.get("hr_scale"):
            hr_params.append(f"Hires upscale: {scale}")
        if steps := payload.get("hr_second_pass_steps"):
            hr_params.append(f"Hires steps: {steps}")
        if upscaler := payload.get("hr_upscaler"):
            hr_params.append(f"Hires upscaler: {upscaler}")
        if hr_params:
            lines.append(", ".join(hr_params))

    # 版本信息
    lines.append("Version: v1.10.1")

    # 最终格式处理
    parameters="\n".join(lines).replace("\n", ", ", 1).replace("\n", ", ").replace(", , ", ", ")
    parameters=prompt+parameters
    pnginfo = PngImagePlugin.PngInfo()
    pnginfo.add_text("parameters",parameters)
    return pnginfo
#生成图片文件，输入参数：payload，pngInfo，输出文件名
def generate_img(payload,output_file,clone_flag=False):
    if(output_file is None):
        print('生成参考图像中……',end=" ")
    elif(clone_flag == True):
        print('生成克隆图像中……')
    else:
        print("生成参考图像中……")
    #访问webui的api，生成图像文件，并保存pngInfo
    try:
        result_image = requests.post(url=f'{address}/sdapi/v1/txt2img', json=payload)
    except Exception as e:
        print(e)

    if result_image is not None and result_image.status_code != 500:
        image_context = result_image.json()['images'][0]
        image = Image.open(io.BytesIO(base64.b64decode(image_context.split(",",1)[0])))
        if output_file is not None:
            if(clone_flag == False): #如果不是复制，是新生成图像，需要从新图像中生成pngInfo
                seed=str(json.loads(result_image.json()["info"])["seed"])
            else:
                seed=payload.get("seed")
            pnginfo=parse_payload_to_pngInfo(payload,seed)
            try:
                output_file = output_file.replace("-1",str(seed))
                image.save(output_file, pnginfo=pnginfo)
                print(f'{output_file} is saved.')
            except Exception as e:
                print(e)
        return image
    else:
        print('Something went wrong...')
        return None
#用user_image，克隆ref_img
def clone_img(ref_img:Image.Image,user_img:Image.Image):
    payload=generate_payload(ref_img,user_img)
    if(payload is not None):
        output_file=out_dir+"/"+generate_filename(payload,user_img)
        generate_img(payload,output_file,True)
# 生成N张参考图片
def generate_ref_img(n:int=1,save_ref_img:bool=True):
    for i in range(n):
        #读配置文件
        sys_config=load_config("sys_config.txt")
        prompt_config = load_config("prompt_config.txt")
        with open("prompt_group.txt", 'r', encoding='utf-8') as f:
            prompt_groups = json.load(f)
        # 生成提示词
        prompt, neg_prompt = generate_prompts(prompt_config, prompt_groups)
        payload = {
            "prompt": prompt,
            "negative_prompt": neg_prompt,
            "seed": sys_config["seed"],
            "steps": sys_config["steps"],
            "cfg_scale":  sys_config["cfg_scale"],
            "width":  sys_config["width"],
            "height":  sys_config["height"],
            "sampler_index":  sys_config["sampler_index"],
            "scheduler":  sys_config["scheduler"],
            "enable_hr": False, 
            "save_images":False,
            "override_settings": {
                "sd_model_checkpoint" : sys_config["checkpoint"]
            }
        }
        if(save_ref_img == True):
            output_file=ref_dir+"/REF-"+trim_prompt(prompt)+","+str(sys_config["seed"])+".png"
            print(n-i, end=" ")
            return generate_img(payload,output_file)
        else:
            return generate_img(payload,None)
#用user_dir目录下的人脸，克隆ref_dir目录下的参考图片
def clone_images():
    # 初始化列表和队列
    user_images = []
    ref_images = []
    # 读取user目录下的所有图像文件
    for filename in os.listdir(user_dir):
        if filename.endswith(('.png', '.jpg', '.jpeg')):
            file_path = os.path.join(user_dir, filename)
            user_images.append(Image.open(file_path))
    # 读取ref目录下的所有图像文件
    for filename in os.listdir(ref_dir):
        if filename.endswith(('.png')):
            file_path = os.path.join(ref_dir, filename)
            ref_images.append(Image.open(file_path))
    
    n=len(ref_images)*len(user_images)
    i=0
    for ref_image in ref_images:
        for user_image in user_images:
            if(resume_point>n-i):
                print(n-i, end=" ")
                clone_img(ref_image,user_image)
            i=i+1
#随机生成user的图片
def generate_random_images(n:int=1):
    user_images = []
    file_names = []
    # 读取user目录下的所有图像文件
    for filename in os.listdir(user_dir):
        if filename.endswith(('.png', '.jpg', '.jpeg')):
            file_path = os.path.join(user_dir, filename)
            user_images.append(Image.open(file_path))
            file_names.append(filename)
    
    for i in range(n):
        print(n-i, end=" ")
        sys_config=load_config("sys_config.txt")
        user_name=sys_config["user_name"]
        if(user_name==''): #随机
            ref_image=generate_ref_img(1,False)
            user_image=user_images[random.randint(0,len(user_images)-1)]
            clone_img(ref_image,user_image)
        elif(user_name=='all'): #所有
            for user_image in user_images:
                ref_image=generate_ref_img(1,False)
                clone_img(ref_image,user_image)
        else:
            for index in range(len(file_names)):
                if(file_names[index].find(user_name)>=0):
                    ref_image=generate_ref_img(1,False)
                    user_image=user_images[index]
                    clone_img(ref_image,user_image)                

def set_resume_point(n:int):
    resume_point=n
####################################
# 以上是函数，以下是执行具体动作
####################################
def help():
    print("使用方法：")
    print("-ref [N], --reference [N]\t生成N张参考图片，放到ref_dir目录下。")
    print("-ran [N], --random [N]\t\t用user_dir目录下的人脸，随机生成图片。")
    print("-c, --clone\t\t\t用user_dir目录下的人脸，克隆ref_dir目录下的参考图片。")
    print("-r N, --resume N\t\t\t克隆时从第N张开始断点续传，N为最后一个正常克隆的图片序号，需与clone参数同用。")
    print("支持多个参数组合使用，将按顺序调用。例如：-r 99 -c -ran 100 -ref 10")
    
def parse_arguments():
    actions = []
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        
        # 处理 resume 参数
        if arg in ("-r", "--resume"):
            if i+1 < len(sys.argv) and sys.argv[i+1].isdigit():
                num = int(sys.argv[i+1])
                actions.append(lambda: set_resume_point(num))
                i += 2
            else:
                i += 1

        # 处理 clone 参数
        elif arg in ("-c", "--clone"):
            actions.append(lambda: clone_images())
            i += 1
        
        # 处理 reference 参数
        elif arg in ("-ref", "--reference"):
            if i+1 < len(sys.argv) and sys.argv[i+1].isdigit():
                num = int(sys.argv[i+1])
                actions.append(lambda: generate_ref_img(num))
                i += 2
            else:
                actions.append(lambda: generate_ref_img())
                i += 1
        
        # 处理 random 参数
        elif arg in ("-ran", "--random"):
            if i+1 < len(sys.argv) and sys.argv[i+1].isdigit():
                num = int(sys.argv[i+1])
                actions.append(lambda: generate_random_images(num))
                i += 2
            else:
                actions.append(lambda: generate_random_images())
                i += 1
        
        # 处理无效参数
        else:
            return False

    return actions

if __name__ == "__main__":
    actions = parse_arguments()
    
    if not actions:
        help()
    else:
        for action in actions:
            action()
        print("All is done!")