from django.db import models
from sympy import N

from django.contrib.auth.models import AbstractUser


# # create/update 시간 기록
# class TimeStamp(models.Model):
#     update_at = models.DateTimeField(auto_now=True)
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         abstract = True

"""
[Users]
- PK: id
- relation
    - Users : LectureHistory = 1 : n 
"""
# 유저
class Users(AbstractUser):
    id = models.CharField(max_length=20, primary_key=True, null=False, default='')
    # password = models.CharField(max_length=20, null=False)
    # name = models.CharField(max_length=20, null=False)
    # email = models.EmailField(max_length=40, null=False)
 
"""
[LectureHistory]
- PK: (lecture_id, lecture_name)
- FK: id 
- relation
    - Users : LectureHistory = 1 : n 
    - LectureHistory : LectureQuiz = 1 : n 
"""    
# 사용자별 강의 히스토리
class LectureHistory(models.Model):
    # lecture_id = models.ForeignKey(Users, on_delete=models.CASCADE) # Users의 PK를 FK로 받음
    lecture_name = models.CharField(max_length=255, primary_key=True, null=False, default='')
    lecture_url = models.CharField(max_length=255)
    embed_url = models.CharField(max_length=255)
    lecture_note = models.TextField()
    lecture_sum = models.TextField()
    # 각각의 키워드를 comma로 연결해서 하나의 문자열로 저장
    keyword = models.TextField()
    update_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # class Meta:
    #     constraints = [
    #     models.UniqueConstraint(
    #         fields=['lecture_id', 'lecture_name'], name='lecture_id_and_name'
    #     )
    #     ]
    
# """
# [LectureQuiz]
# - PK: (id, lecture_name)
# - FK: (id, lecture_name)
# - relation
#     - LectureHistory : LectureQuiz = 1 : n 
# """
# # 강의 히스토리 내 퀴즈 저장
# class LectureQuiz(models.Model):
#     models.ForeignKey(LectureHistory, on_delete=models.CASCADE)
#     lecture_name = models.CharField(max_length=255)
#     quiz = models.CharField(max_length=255)
#     quiz_answer = models.CharField(max_length=255)
#     quiz_keyword = models.CharField(max_length=255)
    