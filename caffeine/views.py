from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, authenticate, logout
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Count
from regex import P

from caffeine.forms import RegisterForm

import time
import os, os.path
import pyautogui

from .tools.down_movie import downYoutubeMp3, down_title
from .tools.stt import upload_blob_from_memory, transcribe_gcs
from .tools.vision_text import text_detection
from .tools.sum import summary_text, sum_model_load
from .tools.textrank import key_question, load_key_model, plot_keywords

from .models import LectureHistory
from .models import Users

from django.contrib import messages

## 강의 기본 정보 변수
contents = list()
movie_urls = list()
embed_urls = list()
movie_titles = list()
movie_ids = list()

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
    # 메인페이지 강의 추천을 위한 DB READ
    # lecture_name에 따라 count를 한 후
    video_views = LectureHistory.objects.values('lecture_name', 'lecture_url', 'id_url').annotate(
        num_lecture=Count('lecture_name')).order_by(
        '-num_lecture')
    # 가장 많은 제목의 강의들의 강의명과 링크를 반환
    toweb = {"recommend": video_views[:3]}

    return render(request, 'index.html', toweb)


def model(request):  ## 모델 로드 페이지 (속도 개선 위해 임시)

    ## summary 모델 로드
    model_sum, token_sum = sum_model_load()
    models_sum.append(model_sum)
    tokens_sum.append(token_sum)

    ## keybert 모델 로드
    models_key.append(load_key_model())
    return HttpResponse("!!모델로드 완료!!")


@csrf_exempt  # @csrf_exempt: 사이트 간 위변조 방지 토큰
def result(request):  # 결과물 페이지(주소 입력 -> STT,요약등 결과물 출력)
    if request.method == 'POST':
        # 동영상 url 받아오기
        print(request.POST['address'])
        movie_url = request.POST['address']

        # 주소값 수정
        if movie_url.find("&list") >= 1:
            movie_url = movie_url[:movie_url.find("&list")]

        # 주소값 할당
        movie_urls.append(movie_url)
        movie_ids.append(movie_url[movie_url.find("=") + 1:])

        # 동영상 이름 추출
        movie_title = down_title(movie_url).replace(":", " -")
        movie_title = down_title(movie_url).replace("|", "_")
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

        print(context)  # 확인
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

        #시간 측정
        start_time = time.time()
        # 동영상 STT
        gcs_url = "gs://dgu_dsc_stt/"  # 스토리지 path
        gcs_file = gcs_url + contents[-1]  # 스토리지 내 동영상 path
        try:  # STT
            text_all = transcribe_gcs(gcs_file, contents[-1], 44100)
        except:  # STT
            text_all = transcribe_gcs(gcs_file, contents[-1], 48000)
        end_time = time.time()

        # 텍스트 할당
        text_alls.append(text_all)
        print(text_all)
        print("!!STT 소요시간!! : ",round((end_time - start_time), 4))

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
    return code_imgs


@csrf_exempt
def code_to_text(request):
    if request.method == 'POST':

        count = 1

        # 이미지 저장
        x_left = float(88)
        y_up = float(295)
        x_right = float(1214)
        y_down = float(640)
        pyautogui.screenshot('./img/{}.png'.format(count), region=(x_left, y_up, x_right, y_down))

        # 이미지 경로 탐색
        path = os.getcwd()
        #폴더 경로 탐색
        folder_codes = "img"
        folder_path = os.path.join(path, folder_codes)
        # 폴더에 있는 이미지 경로 탐색
        code_imgs = get_code_imgs(folder_path)
        img_path = os.path.join(path, folder_codes, code_imgs[-1])
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


        # gen = {}
        # for idx, code in enumerate(code_text):
        #     gen[idx] = code
        gen = {}
        code_str = ''
        for sentence in code_text:
            code_str = code_str + sentence + '\n'
        gen[0] = code_str
        print(gen)

    return JsonResponse(gen)


@csrf_exempt
def summary(request):  ## 요약문 생성 버튼을 위한 메소드
    if request.method == 'POST':
        temp = """Hi everyone. Today, we will talk about functions and how we can use them to change the text color of your terminal. So we will begin with an overview of functions and we will finish with this quick and fun project to function in their most basic definition of instructions. We use them to perform a specific tasks, for example, and eat cookies, function will include instructions to open mouth insert a cool Chi chew it multiple times and then lastly swallow it. And while each of these actions is a task, when we still bundle them under the umbrella of eat cookies. Now, let's see some fight and examples. First. We Define a function with a deaf Chi Ward. Next. We choose a name for this function in our case multiply with in a data set of round brackets, followed by a Colin and we enter the body of the function. Know the body is always in And it either with a tough character or with a bunch of spaces and the variables, A and B, which we have created, here are only available inside the function. If we'll try to access them from anywhere else. We will get an error. That's why we call them local variables. They are local to our function but are strangers everywhere else lost wave functions. Also have an outcome. In the case of our cookies function. The outcome is getting energized, becoming less hungry or maybe just appreciating The Taste. In the case of our multiple. I function. The outcome or output is a * B and we passed it into something called a return statement. A return statement represents the end of the function. This means that any line of code, we include below. It will not be under the umbrella of multiple. I now a valid return. Statement always includes some kind of data. This could be an integer, a Boolean, a string, a list or any other data type affect, even if we return non, which is the absence of data or an empty void, that still counts, the only case where we can skip the return statement is when we print something, but even our function, still Returns the data of none. We just didn't officially type it, but simply defining a function is not enough. We also need to call it and just like with Youmans, we call a function by its neck X, but I like humans. We also add a set of round brackets to the end of the Skoal know, a function that multiplies the exact same values time. After time is not very useful. What if we want to change the values of a and the values of beat every time. The function sample used something called parameters. Instead of variables, in the following example. We have placed A and B inside the round Rockets. So there are no longer variables. But rather parameters, no parameters are used as placeholders. We get to decide which values they represent. Only when it's time to call the function, not when we Define it. So, let's say we want to move to fly to buy for. In this case, a is a placeholder for 2 +. B is a placeholder for, for know, these numeric values. We see, inside our function, call are actually known as arguments. We use them to assign values to our coronavirus. So parameters, been are basically placeholders for arguments and if we select different Arguments, for example, 8 and 2. We are only Chi Walking the output of the function without changing the function itself. So, it's quickly practice everything. We have learned with a few coating exercises. So, we will Define a new function called about me and this function will take in three different parameters. The first one is named, the second is profession. And the last one would be tapped. Now, inside the body of the function. I would like to print. Hi. My name is to which we will concatenate our very first barometer name then similarly in the next line of code will print. I am a profession and then lastly and I have a pet. We will then leave the body of the function and we can then call it on our own personal information that we want to taste. That would be about me. My name is Maria. My profession is program. ER, and my pet is a cat. We will save this file and we will run it. And once we look in the term, we can see that all our parameters were replaced by their corresponding arguments and in a similar way, we can also call the about me function on CD.  Wizard.  Who has a mighty eagle?  We will save this file. We will rerun it. We will take a look in the terminal where we see the same function returns to different output depending on the arguments cool. But now let's do something a bit more useful. Let's randomly change. The text color of our print statements to do this. We will first import the ram the module and then additionally from sty, which is a console text styling model. We will import f g whereas G stands for foreground or text color and then go ahead and Define our function. We will call it generate RGB.  No RGB use a color mode where we mix between red green and blue. Each of these primary colors has its own intensity and it can be any value in between 0 and 2:55. If you guys want to find out more about it. I have a bunch of tutorials on its already. You can check them out. Now inside the body of the function. We will begin with the intensity of red. Since we are planning to work with random values. We will access the random module. And since this value is going to be an integer. We will fetch the rent in to Method. As in random integer, we will restrict integer to values between 0 and 256 week. And then we feed this across the rest of our color channel. So will copy this line of code. We will taste it below. We will replace red with green and we will do the same thing for our blue Channel.  And then lastly, as a return statement, we will return red green and blue in a tuple. And then ride below. We will exit the body of the function so we can finally call it. So generate RGB, which we will assign to the exact same to Apple. We are returning will just copy these values and we will place them in front of our function code. If we'd like to have a quick look, we can print red, green and blue and then each time. We, we run this code. We are generating brand new values for each of our color channels, but that's not all. We will define an additional function, cold generate color.  And this time we will pass some parameters to it. And as you may guess these parameters would be red, green, and blue and then we will get it to return. A foreground color ft. Based on the same parameters. We have just collected. We can then scroll all the way down and we will call this function right before our print statement. So generous color where we pass red green and blue. Again, we can assign this function call to color.  Interval data model fight our print statement. So instead of printing or color we will simply generated by specifying color and weekend then concatenate. Some kind of a string. Let's say, randomly changing colors, hahaha.  As an evil laugh, we will then save this file, and we will rerun it. And then, once we look at the terminal, it looks so much prettier. If we keep rerouting this code, Google keep generating all kinds of different colors, without really doing much. So once again, we haven't really changed anything inside the function, and this time, we're not even passing different arguments to it. And yet, our function returns a different output, each time we call it, which is awesome. So,  Good job, everyone. And even, if you guys didn't feel like holding along with me, you can always copy my code from the link in the description. Perfect. So, we've seen that the primary goal of functions is to organize our code and to split it in two tasks. But functions are also useful for avoiding repetition. So if we are planning to repeat a block of code, we will simply place it inside a function and reduce it to a single command which will a horse. Save us a lot of typing now. Thank you guys so much for watching. If you found the tutorial, please leave it at like maybe leave me a comment, subscribe to my channel, turn on the notification bill or share it with everybody, you know, code taste again, and I will see you very soon. """

        # 요약문 생성
        sum_text_l = summary_text(temp, models_sum[-1], tokens_sum[-1])

        sum_text = ""
        for i in range(len(sum_text_l)):
            sum_text += '<div class = "box"> <h4>{}</h4> {}<br> </div>'.format((i+1),sum_text_l[i])
        sum_texts.append(sum_text)
        print(sum_text)

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
        key_dict = key_question(text_re, models_key[-1])

        # 동글이 출력
        plot = plot_keywords(key_dict)
        plot_html = '<img style="width=100%;" src="data:image/png;base64, {}"/>'.format(plot)

        # 키워드 추출
        keywords = ''
        hash_tag = ''
        count = 1
        for i in key_dict["keywords"]:
            keywords += str(count) + '순위 : ' + str(i) + '<br>'
            hash_tag += '#' + str(i) + ' '
            count += 1
        print(keywords)
        hash_tags.append(hash_tag)

        # 웹으로 보낼 데이터
        result = {
            "keyword": keywords,
            "sentence_blank1": key_dict["sentence_blank1"],
            "sentence1": key_dict["sentence1"],
            "answer1": key_dict["answer1"],
            "sentence_blank2": key_dict["sentence_blank2"],
            "sentence2": key_dict["sentence2"],
            "answer2": key_dict["answer2"],
            "sentence_blank3": key_dict["sentence_blank3"],
            "sentence3": key_dict["sentence3"],
            "answer3": key_dict["answer3"],
            "sentence_blank4": key_dict["sentence_blank4"],
            "sentence4": key_dict["sentence4"],
            "answer4": key_dict["answer4"],
            "sentence_blank5": key_dict["sentence_blank5"],
            "sentence5": key_dict["sentence5"],
            "answer5": key_dict["answer5"],
            "plot_html": plot_html
        }
    return JsonResponse(result)


@csrf_exempt
def savedb(request):  # DB 저장을 위한 메소드
    if request.method == 'POST':
        if request.user.is_authenticated:
            print(request.user)
            ## history 내에 데이터 있는지 확인 후 없으면 생성
            try: # DB 존재하지 않을 시
                history, cre = LectureHistory.objects.get_or_create(id=str(request.user) + '_' + str(movie_titles[-1]),
                                                                    user_id=request.user, created_at=timezone.now())
                history.lecture_name = movie_titles[-1]
                history.embed_url = embed_urls[-1]
                history.lecture_url = movie_urls[-1]
                history.id_url = movie_ids[-1]
                history.update_at = timezone.now()
                try:
                    history.lecture_note = text_alls[-1]
                    history.lecture_sum = sum_texts[-1]
                    history.keyword = hash_tags[-1]
                    history.save()
                except:
                    history.lecture_note = " "
                    history.lecture_sum = " "
                    history.keyword = " "
                    history.save()
            except: #DB 존재시
                history = LectureHistory.objects.get(id=str(request.user) + '_' + str(movie_titles[-1]))

                history.lecture_name = movie_titles[-1]
                history.embed_url = embed_urls[-1]
                history.lecture_url = movie_urls[-1]
                history.id_url = movie_ids[-1]
                history.update_at = timezone.now()
                try:
                    history.lecture_note = text_alls[-1]
                    history.lecture_sum = sum_texts[-1]
                    history.keyword = hash_tags[-1]
                    history.save()
                except:
                    history.lecture_note = " "
                    history.lecture_sum = " "
                    history.keyword = " "
                    history.save()
            return HttpResponse("!!DB 저장 완료!!")
        else:
            return HttpResponse("!!로그인 필요!!")


@csrf_exempt
def board(request):  # 게시판 출력을 위한 메소드

    page = request.GET.get('page', '1')  # 페이지

    question_list = LectureHistory.objects.filter(user_id=request.user).order_by('-update_at')
    paginator = Paginator(question_list, 10)  # 페이지당 10개씩
    page_obj = paginator.get_page(page)
    context = {'lecture_list': page_obj}
    return render(request, 'board.html', context)


@csrf_exempt
def history_result(request, id):  # 게시판 결과물을 위한 메소드
    # id를 pk로 가지고 오기
    history_lecture = get_object_or_404(LectureHistory, pk=id)
    context = {'history_lecture': history_lecture}

    return render(request, 'history_result.html', context)


# 회원가입
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
        return render(request, 'index.html', {'form': form, 'msg': msg})
    else:
        form = RegisterForm()
        return render(request, 'register.html', {'form': form})


# 로그인
def login_view(request):
    if request.method == 'POST':
        # 유저 존재하는지 검증
        form = AuthenticationForm(request, request.POST)  # Django가 만들어 놓은 Form
        msg = '가입되어 있지 않거나 로그인 정보가 잘못되었습니다.'
        print(form.is_valid)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=raw_password)
            if user is not None:
                msg = 'login success!'
                login(request, user)
        return render(request, 'login.html', {'form': form, 'msg': msg})
    else:
        form = AuthenticationForm()
        return render(request, 'login.html', {'form': form})


# 로그아웃
def logout_view(request):
    logout(request)
    return redirect('index')

# @csrf_exempt
# def test(request):
#     if request.method == 'POST':
#         # 키버트 활용
#         text_re = request.POST['text']
#         key_dict = key_question(text_re, models_key[-1])
#
#         plot = plot_keywords(key_dict)
#     return HttpResponse(plot)
