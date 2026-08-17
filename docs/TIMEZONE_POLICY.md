Timezone & Date Policy
======================

- 저장(보관): UTC 기준(ISO8601 문자열)
- 표시(UI): 로컬 타임존(KST 등)로 렌더링
- 날짜 파싱: `YYYY-MM-DD` 엄격, 시간 포함 시 `YYYY-MM-DDTHH:MM:SSZ`
- 라벨링 기준: 일일 통계는 UTC 00:00 경계, 외부 소스가 로컬 기반이면 주석으로 명시

