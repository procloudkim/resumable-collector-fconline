# ERD: 출전 랭킹(프로젝트2)

```mermaid
erDiagram
  TOP_DAILY_RECORD {
    TEXT    date PK
    INTEGER rank PK
    TEXT    선수_기본정보
    INTEGER 출전
    TEXT    공격_포인트
    TEXT    득점
    TEXT    도움
    TEXT    유효_슈팅
    TEXT    일반_슈팅
    TEXT    패스_성공률
    TEXT    드리블_성공률
    TEXT    공중볼_경합_성공률
    TEXT    가로채기
    TEXT    태클_성공률
    TEXT    차단_성공률
    TEXT    선방_골_차단
    TEXT    평점
  }
```

- 물리 테이블: `top_daily_record` (SQLite)
- PK: (date, rank)
- 입력 경로: `project2/app/parser` → `project2/app/writer.write_db`
- 참고: CSV는 월별 파일(`topdailyrecord_YYYY-MM.csv`)로 동일 스키마 헤더 사용

