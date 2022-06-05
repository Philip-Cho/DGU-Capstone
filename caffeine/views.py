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
        temp = """So where are we? We started off with a simple method for learning stuff.  Then we talked a little about.  Learning approaches to learning that were vaguely inspired by.  The fact that our heads are stuff when they're onto that, we seem to evolve from primates.  Then no, we talked about looking at the problem and address the issue of tautology and how it's possible to learn Concepts.  Have an hour coming full, circle back to the beginning and thinking about how to divide up a space with the fission boundaries. But whereas you do it with a neural net.  Or a nearest neighbors or AI Dee treat. Those are very simple ideas.  Stats work, very often. Today. We're going to talk about  A very sophisticated idea that still has its implementation.  So, this needs to be in the tool bag of every civilized person.  This is about support Vector machines and idea that was developed. While I want to talk to you today about how ideas developed actually, because you look at stuff like this in a book and you think well Latimer vapnek just to figure this out. One Saturday afternoon when it was the weather was too bad to go outside. That's not how it happens. It happens very differently. I'll talk to you a little bit about that.  Nice thinking about.  About things that were three things that were done by people are still alive, is you ask them how they did it. You can't do that with 48. You can't say 248. How did you do it? Did you dream it up on a Saturday afternoon, but you can call that make on the phone and ask questions. That's the stuff. I'm not talk about towards the end of the hour.  Well, it's all about decisions, boundaries. And now we have several techniques that we can use to draw some decision boundaries. And here's the same problem. And if we drew decision boundaries in here, we might get something that would look like maybe this.  If we were doing a nearest neighbor approach, and if we're doing ID trees.  Would just draw in a line like that and if we're doing neural Nets, well, you know, you can put in a lot of straight lines. Hope wherever you like with a neural that depending on how strained up or if you just simply go in there and design hat. So you could, you could do that if you wanted.  And you would think that after people been working on this or stuff for?  50 or 75 years that the other wouldn't be any tricks in the bag left. And that's when everybody got surprised. Because around the early 90s.  Vladimir Bart and I can reduce the ideas. I'm about to talk to you about.  So what that makes says?  Is there something like this here? You have a space?  And you have some negative examples, and you have some positive samples.  How do you divide the positive examples from the negative examples and what he wants to do? What he says we want to do is what we want to draw straight line.  But with straight line is the question. Well, we want to draw straight line.  Do this packet straight line?  Want to wind up like that?  Probably not so hot. How about 1? This is just right here.  Well, that's my separate them, but  seems awfully close to the negative examples.  So, maybe what we got to do is we on a draw, a straight line in here, sort of like this.  And that line is drawn with a view toward putting in.  The widest.  Street.  The separates the positive samples from the negative samples. That's why I called the wireless Street approach. So that makes way of putting in the decision boundary is to put in a straight line, but in contrast with the way, I did treat puts in a straight line, it tries to put the line in in such a way as the separation between the positive and negative examples hat, that street is as wide as possible.  Heights. OH,  You might think to do that in your art project and then let it go with that. And what's the big deal? So what we got to do is we're going to kind of go through why it's a big deal.  so, first of all week, I like to think about  How you would make a decision. Rule that would use that decision down Drake?  So, what am I to ask you to imagine is it? We've got a vector?  Of any length you like constrained to be perpendicular to the median or if you like perpendicular to the gutters is perpendicular to the to the media line of the street. I strong in such a way that that's true. You. We don't know anything about its language yet.  Then we also have some unknown, stay right here, and we have a vector that points to it.  Myself.  So now we're really interested in is whether or not that unknown is on the right side of the street or on the left side of the street.  So what we want to do, if you want a project that Vector you down on the one is perpendicular to the street, because we're then we'll have the distance in this direction or numbers is proportional to the distance and the direction and a and a further out we go. The closer we'll get to being on the right side of the street, or the right side of the street, is not the correct time, but actually the right side of the street so we can do, as we can say.  Hat State, W and. It with you.  I measure whether or not that number is equal to or greater than some constant C.  So number that the dot product has taken the projection on the w.  And the bigger that projection is the further out along this line. The projection will lie, and eventually be so big that hat, that projection crosses, the median line of the street and I will say it must be a positive sample.  Or we can say, without loss of generality.  That the dot product. Plus I'm constant B is equal to or greater than 0, if that's true.  It's a positive sample. So that's her decision rule.  And this.  Is the first in several elements that were going to have to line up to understand what her that this idea called support Vector machines.  So that's the decision Rule and the trouble is we don't know what constantly it to use and we don't know which W to use either.  We know the W has to be perpendicular to the median line of the street.  Are there? Lots of W's that are perpendicular to the median line of the street? Because it can be of any length.  So, you don't have a enough, constrain here to fix a particular be for a particular w?  Are you with me so far?  All right. So what we're going to do next?  And it's by the way we could just by saying seeing + - B.  What we're going to do next is, we're going to lay on some additional constraints with a view toward putting enough constrain on the situation that we cannot actually calculate calculate a being a w.  So, what we're going to say is this.  Hat. Does if we if we look at this quantity. They were checking out to be greater than or less than 0 to make our decision. Then what we're going to do is we're going to say that if we take you and we safely. Products of that and some X plus some positive sample now knows the positive sample.  What type of the dot product of those two vectors and we had day just like out of her decision rule, we're going to want that to be equal to or greater than 1.  Four letter words.  You can be an unknown anywhere on this street, and be just a little bit greater or just a little bit less than zero. But if you're a positive sample, we're going to insist that this decision function gives a value of 1 or greater.  Likewise.  If W. It was negative sample.  It's provided to us that we're going to say that that has to be equal to or less than -1.  All right.  So if you're mine, a sample of one of these two guys, or any of my task sample, a lot, May lie, down here, this function that gives us the decision. Rule must return, -1 or less.  What is the separation of distance here? - 12, + 14. All of the samples?  So, that's cool.  but we're not quite done, because  I don't know. This is carrying around two equations like this kind of paint. So we're going to do is we're going to do some another variable to make things make life a little easier.  Like many things we do.  I want we developed this kind of stuff introducing this variable, is not something that God says, has to be done. It's just a  Monica, what is it between Urdu status additional stuff to do? What to make the mathematics more convenient term mathematical convenience.  So we're going to do is we're going to introduce a variable, why?  Semi such that.  Why Supply is equal to plus one?  For posting apples.  + -1.  Negative samples.  All right, so we're freaks sample. We're going to have a value for this new quantity. We've introduced why and evaluate why is going to be determined by whether it's a positive sample are negative sample, suppose web samples going to be + 1.  This situation up here and 70 - 14 this situation down here. So what we're going to do with this first equation is we're going to multiply it by Wireless to buy.  And I got that is a lexical. I + B is equal to or greater than 1.  I know you don't we're going to do we're going to multiply the the left side of this equation by we're going to multiple us out of this equation by why somebody as well so that the second equation becomes y x x + y + b.  And I would have to do over here. Wait, we multiply this guy. * -1  So, used to be the case is that was less than -1 Sophie x. Minus one that has to be greater than + 1.  Hoopster. Digital processors are the same.  Because of that, introduces the mathematical convenience.  so now we can say,  That's why have I X X Sigma Chi + b.  Well, what we going to do.  Ram.  Oh, do you think? I'm sorry. Thank you.  Yeah, I would have got very far without.  Stats. It was W. It was W thinking, those are all doctors. I'll be soon. Forget to put the little nectar marks on there, but you know what, I mean?  Boss, baby.  And now, let me bring that. That one over to the left side.  Equal to or greater than 0.  All right, breast correction. I think everything's. Okay. We're going to take one more step and we're going to say that. Why? So bye.  X x / x w + b - 1.  You know, it's always got to be able to a greater than zero. But what I'm going to say, is that for  4.  X and Y in the gutter.  So they always got to be greater than zero, but we're going to say, we're going to have the additional constraint that it's going to be exactly zero for all of the samples that end up in the, in the gutters here, on the street. So, the value of that expression is going to be exactly zero for that sample. Exactly. Zero for this sample, this sample, not 04 that samples. All right.  so, that's  Stop number two.  And this is that number one?  Okay, so now we've just got some Expressions to talk about some constraints. And what are we trying to do here? I forgot.  I remember now. We're trying to get, we're trying to figure out how to arrange for the line to be such that the street separating the classes from the minuses as wide as possible.  So maybe we better figure out how we can express the distance between the two gutters.  That's just a repeater are drawing. We got some Midas is here. That plus is out here.  And we got gutters are going down here.  And now we've got a vector here to A minus.  And we've got a lecture here to a plus.  So that some will call that X Plus and this task minus.  So what's the, what's the width of the street?  I don't know yet. But at what we can do is we can take the difference of those two vectors.  And that will be a vector that looks like this, right.  plus minus x minus  So, now, if I only had a unit normal, that's normal to the median line of the street.  If it's a unit normal that I could, just take the dog product that you at normal and this difference factor and that would be the width of the street, right?  So, another words.  If I had a unit Vector in that direction and I could just drop the two together and that would be the width of the street.  So let me write that down before I forget. So the web.  is equal to x + - x -  okay.  That's the difference nectar. And now I got a multiple by unit Vector but wait a minute. I said that that W. Is it a normal right? W is a normal.  So, what I can do is I can multiply this.  X w and I will divide by the magnitude of you and that will make him the unit vector.  so that  not.  That. Product not a not a product that. Product is, in fact, a scalar. And it's the width of the street.  don't do as much good because  doesn't look like we get much out of it.  Oh, but I don't know. Let's see. Why can't we get out of it?  OT, you know, we got this equation over here.  This is equation that constrains the samples that lie in the gutter.  So if we have a positive sample, for example, then this is fuss one. And we have this equation.  So, it says that X Plus.  X w.  Is equal to.  01 - B.  Hey, I'm just taking this part here. This Defector here, and I'm dying it with X Plus.  So that's this piece right here. Why is one for this kind of sample? So I'll just take the one in the very back over to the other side. I've got 1 - B  Well, we can do the same track with ex-.  If he's got a negative sample.  Then why? So I is negative.  That gives us our negative.  W x. It was extra by  I know we take this stuff back over to the right side and we get 1 - b 1 + b.  So that's all licenses to rewrite this thing as too over the magnitude of w.  How did I get there? Well, I decided I was going to enforce this constraint.  I noted that the width of the street is got to be this different Spectre X and unit Vector. Then I use the constraint plug back some values here and it discovered to my delight and amazement at the width of the street is two over the magnitude of w.  Desperate.  Yeah.  Let's see if I've got a minus here and that makes that - node to be is my task to my take the bo, the other side of becomes Plus.  Data, not going to sign this. This expression here is 1 - 1 + b.  Trust me, it works.  I haven't got my legs all tangle up like last Friday, but not yet. Anyway.  It's possible. There's a lot of algebra.  So this binary here, this is Miracle. Number 3. This just want to hear is the width of the strait.  And what we're trying to do, is, we're trying to maximize that, right.  We want to maximize to over.  The magnitude of WD-40 to get the widest Street under the constraints that we've decided we're going to work with.  All right, so that means that it's okay.  To maximize.  1 /.  Double U instead.  We just dropped the constant and that means that it's okay to minimize.  Analysis of w.  And that means that it's okay to minimize.  1/2 * 11 to the W Squared. Right Brett. Why did I do that?  Why do they multiply by half inch square?  Elizabeth matically convenience. Thank you.  So this is a this is play number 3 in the development.  So, where do we go? We we we decided that was there going to be a decision rule. When I see which side of the line were on, they decided to constrain the situation. So that the value of the decision rule is plus one in the gutters for the positive samples, and -1 in the gutters for the negative samples. And then we discovered it maximizing, the width of the street. Let us, especially like that, which we wish to maximize.  How are you? How are you going to take a break? So we get coffee too bad. We can't do that in this kind of situation, but we what if we put and I'm sure when I got to this point he went out for coffee.  So now we back up and we say, well, let's let these Expressions start developing into a song.  But not like that. That's vapid. Speaking of that neck.  What song is it going to sing the data expression here that would like to find the minimum of the extreme amount of. And we've got something strange here.  That we would like to honor.  What are we going to do?  Let me input. What we're going to do to you. Is it a form of a puzzle?  Is it got something to do?  Was lashaundra.  Has it got something to do with lip gloss?  Or does it have something to do with the grinds? She says, La Grange actually, all three were said to be on for a doctoral defense committee must have been quite an exam, but we want to talk about LaGrange because we got a situation here. This 1801 18 02, 1802.  We learning 1802 that if we going to find the extreme of a function.  With constraints.  Then we're going to have to use a log log into multiple layers.  Have a good one, a new expression.  Which we can maximize or minimize without thinking about the constraints anymore. That's how the garage multiple layers work.  So, this brings us to Miracle number 4.  Piece of the developmental Pace number for data stored. It works like this.  We're going to say the L that they were going to try to maximize in order to maximize the width of the street is equal to 1/2.  Time's the magnitude of that. Vector W squared.  -.  and now we got to have  A summation of Rowlett, constraints.  I need to those constraints is going to have a multiplier Alpha Sigma Chi.  And then we write down the constraint.  I will write down the constrained. There it is up there, but I've got to be hyper careful here cuz otherwise I'll get lost in the algebra. So the constrained is why survive?  X Vector W. It with your ex, so bye.  Plus b. And now I've got a closing parenthesis. A - 1. That's the end of my constraint.  I saw.  I sure hope I've got that right, cuz I'll be in deep trouble if that's wrong. Anybody see? Any bugs? That looks like we got that. We got the original thinking, we're trying to work with now. We got into multiple all X track, a train up there, where each constraint is constrained to be 0.  Well, there's a little bit of mathematical sleight-of-hand here because in the end, the ones that are going to be zero. The LaGrange multipliers here, the ones that are going to be 90 or going to be the ones connected with factors that lie that got her. The rest are going to be 0.  What are any event?  We can pretend that this is what we're doing and then we got to find a Max. I don't care whether it's a maximum or minimum lost track, but we're going to do is work on trying to find an extreme wave that. So what do we do? 1801 teachers about  Find maximum. We got to find the derivative and set them to zero.  And then after we've done a little bit of that manipulation, we're going to see a wonderful song start to emerge. So I'll see if we can do it. Let's take the partial of el. Grange in respect to the vector w o my God, how do you differentiate with respect to a vector?  Turns out that it has a form. That looks exactly like differentiating respect with scalar and wave, prove that to yourself as you just expand everything. In terms of all the doctors components, you differentiate those would expect what your differentiating expect to and everything. Turns out the same.  so what you get when you differentiate this was specters Vector W, it is  Two thumbs down. I mean have just  92w.  Yeah, like so.  Not tonight affect w.w.  Like so no magnitude involving.  Then we got a w over here and we got her weekend. So we got different Chi, this part of the Spectre W as well, but that farts a lot easier to do. We have there is a w. It's not there's no magnitude has not raised any power. So what's w x?  12 * x, + y, Savannah and Alpha Sigma Chi.  Thanks, that's means that this expression is derivative with respect to w w the song, Alpha Sigma Chi.  Why should I?  Pixel art.  And that's how I got to be set to 0.  And that implies the w.  Is equal to the sum?  Poisson Alpha Isom. Scalars X is -1 or + 1 variable x x /.  All right.  And now, the math is beginning to sing.  Because it tells us that the vector w.  Is a linear, some of the samples, some some, all the samples are some of the samples.  It didn't have to be that way.  It could have been raised to a power that could have been a logarithm. All sorts of horrible, things could have happened when we did this. But when we did this, we discovered that W is going to be equal to a linear some of these vectors here.  Some of the vectors in the sample set. And I say something because we're for some Alpha will be zero.  So, this is something that we want to take note of and something important.  Now.  Of course, we got to differentiate Elvis back to anything else that might vary. So we got to differentiate Elvis back to be as well.  So what's I find equal to?  Well, there's no be in here. So that makes no contribution.  This is Bart here. Doesn't have a v in it. So that makes no contribution. There's no be over here. So that makes no contribution. So we got Alpha, Chi, Chi X Wireless. Have I?  X b.  That has a contribution. So that's going to be the sum of alpha. I x y survive.  Then we differentiate we differentiate was back to be so that just appears, there's a minus sign here and that's equal to 0 or that implies that the some of the alpha I have wireless to buy is equal to 0.  That looks like that might be helpful somewhere.  Data. Now it's time for more coffee. By the way, these coffee. Take months, you stare at it. You work on something else. You got to worry about your finals and thinking about it some more and eventually you come back from coffee and do the next thing.  What is the next thing they were trying to find?  the minimum for,  And you know, you said yourself. This is really a job for the numerical analyst, those guys know about this sort of stuff.  Because of that power in there, that's where this is, a so-called quadratic optimization problem.  So this point you would be inclined to Hannah's problem with the numerical analysis. They'll come back in a few weeks with an algorithm evil met the algorithm and maybe things work. Maybe they don't coverage. But any case you don't worry about it.  We're not going to do that because we want to do a little bit more math because we're interested in stuff like this.  Retrofitting the fact that the decision Vector is a linear some of the samples. So we're going to work a little harder on this stuff and in particular now that we've got an expression for w, this one right here. We're going to plug it back in there and we're going to plug it back in here and see what happens to that thing. We're trying to find the extreme them up.  Is it right kind of relaxed taking deep breath?  This is exactly. This is the easiest part. This is just something just doing a little bit of the algebra.  So, the thing we're trying to to maximize or minimize is equal to 1/2.  And now we got to have that label the magnitude of those. The Matrix to here.  Interval dinner twice.  Hi code for multiple entities together.  So, let's see what we've got.  From that expression up there. One of those W's will just be the some of the alpha, i x Wireless to buy, X affect your ex and Vine.  And then we got the other one too. So that's just going to be the sum of alpha. No, I want to keep things. I'm going to take Ashley to label a switch. Those two subs together into a double summation. So I have to keep the index of straight.  So, I'm just going to write that is Alpha stim. Jayraj xcj.  So, those are my two factors and one take the top product for those. That's the first piece, right?  For this is. So this is not, this is hard, so minus. And now the next term.  Looks like a f. I y Sol by y x w, so you got a whole bunch of these are, some of alpha I want to buy has extra line, and then it gets multiple times W. So put this like this song, alpha jyj, ask Sanjay and they're like that and then that's it. Product.  Classes that wasn't as bad as I thought.  Now, I've got to deal with the next term. The alpha, i x Wireless. Have i x? A b.  So that's my that's a - some of alpha. I x y. So i x b.  And then finish it off. We have plus the song.  The Alpha Sigma Chi has one up there, might as one in front of the summation such as the sum of the alphas. Are you with me so far? Just a little algebra.  It looks good. I think I'm, I think I haven't left it yet.  Let's see.  Alpha, i x Wireless wave items. BB is a constant. So pull that out there and then I just got to some of those outfits to buy X, Wireless to buy.  Oh, that's good at zero.  And also. So for every one of these times we thought it was this whole expression.  So that's just like taking this thing here.  And and data nodes two things together, right?  Oh, but that's just the same thing. We've got here.  so, now what we can do is we can say that we can rewrite this lagrangian as  We got the Hat, some of Alpha Chi.  Hat deposit on it.  And I know we got we got one of these and a half of these, so that's -1/2. And now I just can read that whole works into a double thumb over both, I and J of alpha on at times.  Alpha Jay, I was why so violent. As why such a chi chi.  What's the weather in a lot of trouble to get there? But now we've got it. And we know that what we're trying to do is we're trying to find a maximum of that expression.  And that's the one we're going to hand off to the miracle analyst.  So we're going to hand this off to the numerical analysis. Anyway, why did I go to all this trouble?  Good question.  Want to do you have any idea why I went to all this trouble.  Because I wanted to find out the dependent on this expression. As one is telling me as I am, as light as I got a chi chi in Romania. I want to find what this maximization depends on, with respect to the the days of the suitcase, vectors the extra, the sample vectors. And what I've discovered is,  Hat, the optimization.  Depends only on the dock product of pairs of samples.  That's what we want to keep in mind. That's why I put it in, Royal Purple.  The up here. So, so let's say, you know what, we call that one up there. That's too, I guess this will call this piece here 3. This piece here is for and out of one more piece.  Cuz I want to take that, that w.  And I don't like thinking back into that lagrangian. I want to stick it back into the decision rule.  So now my decision rule with this expression for w.  Is it going to be W plugged into that thing?  So, the decision rule is going to look like the some.  The alpha. I x. Y. Z y x.  Hexagon.  Dotted with the unknown Vector life. So  And we're going to subtract. I guess I'd be that way to say if that's greater than or equal to 0.  Then.  Plus.  So, you know, it's easy to see why the mathematics is being the same to us now, because now we discover that the decision rule. Also depends only on the dock product of those sample vectors and the unknown.  The total data total dependence of all of the math on the dock products.  Chi.  And now I hear whisper.  Someone is saying.  I don't believe the mathematicians can do it. I don't think those numerical analyst can find the optimization.  I want to be sure of it. Give me ocular proof, so like to run a demonstration of it.  Okay, there's our sample problem when I started the hour out with. Now if if the optimization algorithm.  It doesn't get stuck in a local maximum or something. You should find a nice straight line separating. Those two guys to finding the widest Street between the minus is in the classes.  So in just a couple of steps, you can see down there, Step 11 has decided that is done as much as I can on the optimization.  And it's got three Alphas.  You can say that the two-  22 - 4 samples, both figure into the solution, the weights on the language in multiple layers are given by those little yellow bars. So the two negatives of participating as one of the positives, but the other positive doesn't, but has a 08  Everything worked out. Well, now I said as long as it doesn't get stuck in the local maximum. Guess what? Those mathematical friends of ours and tell us and prove to us that this thing is a convex space. That means I can never get stuck in a local Maxima.  So in contrast with things like neural Nets were, where were you have a plague of local Maxima? This guy never gets stuck in a local Maxima. Let's try some other examples.  Crystal vertical points. No surprises there, right?  How do we say? Well, maybe you can't deal with diagonal points. Sure can.  How about that?  This thing here.  Yeah, it only needed two of the points.  Since any, any two of those pluses, any to a plus and minus fuel to find the street.  Let's try this Chi.  Oh.  I think what happened here.  My wireless code, right? Because it's linearregression sample.  AI news.  So is situations where is linear layer on separate bowl that the mechanism struggles and eventually we'll just slow down and you trying to get it because it's not making any progress. And you see the red light, the red dots, there are ones that I got wrong.  so it's a well too bad for our side, doesn't look like it's all that good anyway, but then  A powerful idea. Comes to the rescue.  I'm stuck switch to another perspective.  So we don't like the space. The very end because it predicted to go to the samples that are not linear layer, acceptable, acceptable. Then we can say shoot. Here's our space.  Here are two points.  Here are two other points.  I can't separate them. But if I can somehow get them into another space, maybe we can separate them because they look like  Yes.  And the other space and they're easy to separate.  So what we need then?  Is a transformation that will take us from the space. We're in into a space where things are more convenient. So we're going to call that transformation fee for the doctor actually.  Has the transformation. And now, here's the reason for all the magic.  I said,  The maximization only depends on. Products.  So all I need to do the maximization is the is the transformation of one, vector started with the transformation of another doctor.  Myself, that's what I need to maximize.  How to find the maximum log.  Then, in order to recognize, where do they go?  Underneath the chalkboard.  Oh, yeah, sure. It is to recognize. All I need is. Product to. So for that one I need.  Are there. It will be of you and just to make this a little bit more consistent and I'll taste all call a task Jay and the Saxon by. And that's actually why those are the quantities I need in order to do it.  so that means that if I have,  a function, let's call it K of X of I  nxnja.  A sequel to fee. A vexed, survive knotted, next to Jay.  And I'm done. This is what I need.  I don't actually need this.  All I need is that function K. Which happens to be called? A kernel function, which provides me with the dot product of those two vectors in another space? I don't have to know the transformation into the other space.  And that's the reason that this stuff is a miracle.  So what are some of those, what are some of the kernels that are popular? What is the linear kernel? And says that you doubted with me, plus one, the AI is such and such a kernel cuz it's got you in it and being it the two. The two vectors. This is what the dot product is in the other space. So that's one choice. Another choice is a kernel. It looks like this E2. The - let's take the dot product of those two. Are the difference of those two guys.  Affect the magnitude of that and /, some Sigma. That's a second kind of Kernel that we can use.  So let's go back and see if we can solve this problem by transforming into another space where we have another perspective.  Solace.  That's that's that's it. That's it. That's it. That's another kernel.  And so sure we can and that's the answer when transform back into the original space. We could also try doing that with a so-called radial basis kernel, that's the one with the exponential in it. If the learning on that one, no problem.  So you got a general method, that's convection. Guaranteed to produce a global solution.  We got a mechanism that usually allows us to transform this into another space.  So it works like a charm, of course, it doesn't remove all possible problems.  Look at that, exponential thing here.  If we choose a sigma.  That is small enough, and those signals are essentially shrunk, right? Around the sample points and we can get overfitting.  So doesn't immunize against overfitting but doesn't mean I just against local Maxima and does supervised for the general mechanism for doing a transformation into another space with a better perspective. Now, the history lesson, all this stuff feels fairly new. It feels like it's younger than you are.  Here's the history of it that make emigrated from the Soviet Union to the United States in about 1991. Nobody ever heard of this stuff before he emigrated. He actually had done this work on the basic support Factor idea.  It is PhD thesis at Moscow University in the early 60s.  I wasn't possible for him to do anything with it because I didn't have any computers, that you could try anything out with.  So he spent the next 25 years. It's on College Institute in the Soviet Union, doing applications.  Somebody from Bell, Labs discoveries in bytes him over to the United States. Squared sensibly decides to immigrate in 1992 or thereabouts. That makes submits three papers to the nips, the neural information processing systems Journal. All of them were rejected. He still sore about it, but it's motivated.  Around 1990 to 1993 LS1 digits in handwritten character, recognition, and in neural Nets.  That makes things that neural Nets.  What would be a good word to use?  I can think of the vernacular, but he thinks that they're not very good.  So he better call it a good dinner. That support Vector machines will eventually do better handwriting recognition the neural Nets.  That's a dinner BET. Right? It's not that big a deal that is Napoleon said, it's amazing. What a soldier will do for a bit of ribbon.  So, that makes colleague who's working on this on this, on this problem handwritten recognition decides to try a support Vector machine with a kernel in which n equals to.  Just slightly nonlinear works like a charm.  Has it wasn't the first time anybody try to Kernel that make actually had the idea in his thesis but never thought it was very important.  As soon as it was shown to work in the early 90s.  On the problem had already recognition data, resuscitated the idea of the kernel began to develop it and became an essential part of the whole approach of using support Vector machines. So, the main point about this is that it was 30 years in between the concept and anybody ever hearing about it. It was 30 years between that makes  Understanding of kernels and his appreciation of their importance and that's the way things off and go great ideas, followed by long periods of nothing happening. I would buy an epiphany. This moment when the original idea is seem to have great power with just a little bit of a Twist and then the world ever looks back and bat, Mech, but nobody ever heard of until the early 90s become famous for something that everybody knows about today, who does machine learning """

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
        print(request.text)
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
def recommandsave(request):  # DB 저장을 위한 메소드
    if request.method == 'POST':
        if request.user.is_authenticated:
            print(request.user)
            lecture_name_t = request.POST["text"]
            history_lecture = LectureHistory.objects.get(lecture_name=str(lecture_name_t).strip())

            ## history 내에 데이터 있는지 확인 후 없으면 생성
            try: # DB 존재하지 않을 시
                history, cre = LectureHistory.objects.get_or_create(id=str(request.user) + '_' + str(history_lecture.lecture_name),
                                                                    user_id=request.user, created_at=timezone.now())
                history.lecture_name = history_lecture.lecture_name
                history.embed_url = history_lecture.embed_url
                history.lecture_url = history_lecture.lecture_url
                history.id_url = history_lecture.id_url
                history.update_at = history_lecture.update_at
                try:
                    history.lecture_note = history_lecture.lecture_note
                    history.lecture_sum = history_lecture.lecture_sum
                    history.keyword = history_lecture.keyword
                    history.save()
                except:
                    history.lecture_note = " "
                    history.lecture_sum = " "
                    history.keyword = " "
                    history.save()
            except: #DB 존재시
                history = LectureHistory.objects.get(id=str(request.user) + '_' + str(history_lecture.lecture_name))

                history.lecture_name = history_lecture.lecture_name
                history.embed_url = history_lecture.embed_url
                history.lecture_url = history_lecture.lecture_url
                history.id_url = history_lecture.id_url
                history.update_at = history_lecture.update_at
                try:
                    history.lecture_note = history_lecture.lecture_note
                    history.lecture_sum = history_lecture.lecture_sum
                    history.keyword = history_lecture.keyword
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


@csrf_exempt
def index_result(request, lecture_name):  # 게시판 결과물을 위한 메소드

    # id를 pk로 가지고 오기
    history_lecture = LectureHistory.objects.filter(lecture_name=lecture_name).order_by('-update_at')

    context = {'history_lecture': history_lecture[0]}

    return render(request, 'index_result.html', context)

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
