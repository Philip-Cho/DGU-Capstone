from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, authenticate, logout
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.auth.forms import AuthenticationForm

from caffeine.forms import RegisterForm

import os, os.path


from .tools.down_movie import downYoutubeMp3, down_title
from .tools.stt import upload_blob_from_memory, transcribe_gcs
from .tools.vision_text import text_detection
from .tools.sum import summary_text, sum_model_load
from .tools.textrank import key_question, load_key_model

from .models import LectureHistory
from .models import Users

## 강의 기본 정보 변수
contents = list()
movie_urls = list()
embed_urls = list()
movie_titles = list()

## 텍스트 추출 변수
text_alls = list()

## 요약 변수
models_sum = list()
tokens_sum = list()
sum_texts = list()

## 키워드 추출 변수
models_key = list()
hash_tags = list()
## 이미지 추출 변수
code_imgs = list()


def index(request):  ## 인덱스 페이지(주소창 있는 화면)
    return render(request, 'index.html')


def model(request):  ## 모델 로드 페이지 (속도 개선 위해 임시)

    ## summary 모델 로드
    model_sum, token_sum = sum_model_load()
    models_sum.append(model_sum)
    tokens_sum.append(token_sum)

    ## keybert 모델 로드
    models_key.append(load_key_model())
    return HttpResponse("!!모델로드 완료!!")


@csrf_exempt # @csrf_exempt: 사이트 간 위변조 방지 토큰
def result(request):  # 결과물 페이지(주소 입력 -> STT,요약등 결과물 출력)
    if request.method == 'POST':

        # 동영상 url 받아오기
        print(request.POST['address'])
        movie_url = request.POST['address']
        movie_urls.append(movie_url)

        # 동영상 이름 추출
        movie_title = down_title(movie_url).replace(":", " -")
        movie_titles.append(movie_title)

        # 파일 이름 정의
        content = movie_title + '.flac'
        contents.append(content)

        # 임베딩 링크 생성
        embed_url = movie_url.replace('watch?v=', "embed/")
        embed_urls.append(embed_url)

        # 웹으로 보낼 데이터
        context = {
            'embed_url': embed_url,
            'movie_title': movie_title,
        }
    return render(request, 'result.html', context)


@csrf_exempt
def text(request):  # STT 버튼 호출시 실행
    if request.method == 'POST':

        # 동영상 다운
        downYoutubeMp3(movie_urls[-1])

        # 동영상 path가져오기
        path = os.getcwd()
        folder_yt = "yt"
        file_path = os.path.join(path, folder_yt, contents[-1])
        print(file_path)

        # 동영상 스토리지 업로드
        upload_blob_from_memory("dgu_dsc_stt", file_path, contents[-1])

        # 동영상 STT
        gcs_url = "gs://dgu_dsc_stt/"  # 스토리지 path
        gcs_file = gcs_url + contents[-1]  # 스토리지 내 동영상 path
        try:  # STT
            text_all = transcribe_gcs(gcs_file, contents[-1], 44100)
        except:  # STT
            text_all = transcribe_gcs(gcs_file, contents[-1], 48000)

        # 텍스트 할당
        text_alls.append(text_all)
        print(text_all)

        # 웹으로 보낼 데이터
        gen = {
            'text_all': text_all,
        }

    return JsonResponse(gen)


# codes 폴더에 있는 모든 이미지 캡처 순서대로 정렬 후 불러오기
@csrf_exempt
def get_code_imgs(path):
    file_list = os.listdir(path)
    code_imgs = sorted(file_list)


@csrf_exempt
def code_to_text(request):
    if request.method == 'POST':

        # 이미지 경로 탐색
        path = os.getcwd()
        print(path)
        folder_codes = "codes"
        get_code_imgs(path + '/' + folder_codes)
        img_path = os.path.join(path, folder_codes, code_imgs[-1])
        print(img_path)
        code_text = list()

        """
        코드 저장
        - 코드는 한줄씩을 값으로 하는 리스트 형태로 저장됨
        """
        try:
            code_text = text_detection(img_path)
        except:
            print('no code text detected')
            code_text = text_detection(img_path)

        print(code_text)

        gen = {}
        for idx, code in enumerate(code_text):
            gen[idx] = code

    return JsonResponse(gen)


@csrf_exempt
def summary(request):  ## 요약문 생성 버튼을 위한 메소드
    if request.method == 'POST':

        # 요약문 생성
        sum_text = summary_text(text_alls[-1], models_sum[-1], tokens_sum[-1])
        print(sum_text)

        sum_texts.append(sum_text)
        # 웹으로 보낼 데이터
        result = {
            "sum_text": sum_text
        }
    return JsonResponse(result)


@csrf_exempt
def keytext(request):  # 키워드 추출을 위한 메소드
    if request.method == 'POST':

        # 키버트 활용
        text_re = request.POST['text']
        print(text_re)
        key_dict = key_question(text_re, models_key[-1])

        # 키워드 추출
        keywords = ''
        hash_tag = ''
        count = 1
        for i in key_dict["keywords"]:
            keywords += str(count) + '순위 : ' + str(i) + '<br>'
            hash_tag += '# ' + str(i) +',  '
            count += 1
        print(keywords)
        hash_tags.append(hash_tag)
        # 웹으로 보낼 데이터
        result = {
            "keyword": keywords,
            "sentence_blank": key_dict["sentence_blank"] + '<br><br><br><br>',
            "sentence": key_dict["sentence"] + '<br><br>',
            "answer": key_dict["answer"]
        }
    return JsonResponse(result)


@csrf_exempt
def savedb(request):  # DB 저장을 위한 메소드
    if request.method == 'POST':
        # user
        user = Users()
        user.id = "shim2"
        user.username = "shimjongsoo"
        user.save()

        ## history
        history = LectureHistory()
        history.lecture_id = get_object_or_404(Users, id="shim2")
        history.lecture_name = movie_titles[-1]
        history.embed_url = embed_urls[-1]
        history.lecture_url = movie_urls[-1]
        history.lecture_note = text_alls[-1]
        history.lecture_sum = sum_texts[-1]
        history.keyword = hash_tags[-1]
        history.update_at = timezone.now()
        history.created_at = timezone.now()
        history.save()

    # 요약본 출력
    return HttpResponse("!!DB 저장 완료!!")


@csrf_exempt
def board(request):  # 게시판 출력을 위한 메소드

    page = request.GET.get('page', '1')  # 페이지

    question_list = LectureHistory.objects.order_by('id')
    paginator = Paginator(question_list, 10)  # 페이지당 10개씩
    page_obj = paginator.get_page(page)
    context = {'lecture_list': page_obj}

    return render(request, 'board.html', context)

@csrf_exempt
def history_result(request,id):  # 게시판 결과물을 위한 메소드

    history_lecture = get_object_or_404(LectureHistory, pk=id)
    context = {'history_lecture': history_lecture}

    return render(request, 'history_result.html', context)


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        msg = 'Wrong Data'
        if form.is_valid():  # 비밀번호 길이 만족하는지 등
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            msg = '회원가입 완료!'
        return render(request, 'register.html', {'form': form, 'msg': msg})
    else:
        form = RegisterForm()
        return render(request, 'register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, request.POST) # Django가 만들어 놓은 Form
        msg = '가입되어 있지 않거나 로그인 정보가 잘못되었습니다.'
        print(form.is_valid)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            # id = form.cleaned_data.get('id')
            raw_password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=raw_password)
            # user = authenticate(id=id, password=raw_password)
            if user is not None:
                msg = 'login success!'
                login(request, user)
        return render(request, 'login.html', {'form': form, 'msg': msg})
    else:
        form = AuthenticationForm()
        return render(request, 'login.html', {'form': form})
        
def logout_view(request):
    logout(request)
    return redirect('index')