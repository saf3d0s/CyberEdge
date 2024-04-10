import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import PathScanJob  # 确保正确导入PathScanJob模型
from .tasks import scan_paths  # 确保从你的Celery任务模块导入scan_paths

@csrf_exempt  # 允许跨站请求
@require_http_methods(["POST"])  # 限制只接受POST请求
def scan_paths_view(request):
    try:
        # 解析请求体中的JSON
        data = json.loads(request.body.decode('utf-8'))
        wordlist = data.get('wordlist')
        url = data.get('url')
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的JSON格式'}, status=400)

    if not wordlist or not url:
        return JsonResponse({'error': '缺少必要的wordlist或url参数'}, status=400)

    # 异步执行ffuf扫描任务
    task = scan_paths.delay(wordlist, url)

    # 返回响应
    return JsonResponse({'message': '路径扫描任务已启动', 'task_id': task.id})

@csrf_exempt
@require_http_methods(["POST"])
def path_task_status_view(request):
    try:
        # 解析请求体中的JSON
        data = json.loads(request.body.decode('utf-8'))
        task_id = data.get('task_id')
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的JSON格式'}, status=400)

    if not task_id:
        return JsonResponse({'error': '缺少必要的task_id参数'}, status=400)

    # 尝试从数据库获取PathScanJob实例
    try:
        path_scan_job = PathScanJob.objects.get(task_id=task_id)
    except PathScanJob.DoesNotExist:
        return JsonResponse({'error': '任务ID不存在'}, status=404)

    # 构造响应数据
    response_data = {
        'task_id': task_id,
        'task_status': path_scan_job.get_status_display(),
    }

    if path_scan_job.status in ['C', 'E']:  # 如果任务已完成或遇到错误
        response_data['task_result'] = {
            'results': list(path_scan_job.results.values('url', 'content_type', 'status', 'length')),
            'error_message': path_scan_job.error_message
        }

    return JsonResponse(response_data)

@csrf_exempt
@require_http_methods(["GET"])  # 修改为接受GET请求
def get_all_tasks_view(request):
    # 获取所有ScanJob实例的概要信息
    tasks = PathScanJob.objects.all().values('task_id', 'target', 'status', 'start_time', 'end_time')
    tasks_list = list(tasks)

    # 返回响应
    return JsonResponse({'tasks': tasks_list}, safe=False)  # safe=False允许非字典对象被序列化为JSON