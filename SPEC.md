# NTIndex

NeonTeam의 Model Swap 영상을 수집, 정규화, 검색 가능한 형태로 제공하는 정적 사이트 생성기.

## 목표

다음과 같은 제목 형식의 영상을 자동으로 수집한다.

```text
A as B | Game Model Swap
```

예:

```text
Furina as Nahida | Genshin Impact Model Swap
```

수집된 데이터는 SQLite에 저장되며, 이후 정적 HTML 및 JSON 파일로 빌드된다.

---

# 아키텍처

```text
YouTube
↓
Crawler
↓
SQLite (Origin of Truth)
↓
Builder
↓
JSON
↓
HTML/CSS/JS
```

SQLite가 유일한 원본 데이터 저장소(Origin of Truth)이다.

JSON 및 HTML은 모두 산출물(artifact)이며 직접 수정하지 않는다.

---

# 데이터베이스 구조

## games

게임 목록

```sql
CREATE TABLE games (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
```

---

## characters

게임별 캐릭터 목록

```sql
CREATE TABLE characters (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    game_id INTEGER NOT NULL,

    UNIQUE(name, game_id),

    FOREIGN KEY(game_id)
        REFERENCES games(id)
);
```

같은 이름의 캐릭터가 다른 게임에 존재할 수 있다.

예:

```text
Character A (Game X)
Character A (Game Y)
```

는 서로 다른 캐릭터로 취급한다.

---

## videos

수집된 영상

```sql
CREATE TABLE videos (
    id INTEGER PRIMARY KEY,

    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    game_id INTEGER NOT NULL,

    title TEXT NOT NULL,
    link TEXT NOT NULL UNIQUE,

    published_at TEXT,
    crawled_at TEXT NOT NULL,

    FOREIGN KEY(source_id)
        REFERENCES characters(id),

    FOREIGN KEY(target_id)
        REFERENCES characters(id),

    FOREIGN KEY(game_id)
        REFERENCES games(id)
);
```

---

## 인덱스

```sql
CREATE INDEX idx_videos_swap
ON videos (
    game_id,
    source_id,
    target_id
);
```

---

# 크롤링

명령:

```bash
ntindex crawl
```

동작 순서:

1. NeonTeam 채널의 영상을 가져온다.
2. URL(link)이 이미 등록되어 있는지 확인한다.
3. 이미 존재하면 건너뛴다.
4. 제목을 파싱한다.

예:

```text
Furina as Nahida | Genshin Impact Model Swap
```

결과:

```text
source = Furina
target = Nahida
game   = Genshin Impact
```

5. game이 존재하는지 확인한다.
6. 없으면 새로 생성한다.
7. source character가 존재하는지 확인한다.
8. 없으면 새로 생성한다.
9. target character가 존재하는지 확인한다.
10. 없으면 새로 생성한다.
11. videos에 등록한다.

---

# 빌드

명령:

```bash
ntindex build
```

동작:

1. SQLite를 읽는다.
2. 검색용 JSON 생성
3. 게임 페이지 생성
4. 메인 페이지 생성
5. 정적 사이트 출력

예:

```text
dist/
├── index.html
├── search.json
└── game/
    ├── genshin-impact.html
    ├── honkai-star-rail.html
    └── ...
```

게임별 HTML은 해당 게임으로 필터링된 진입점 역할을 한다.

캐릭터별 HTML은 생성하지 않는다.
캐릭터 검색, source/target 필터, A as B 조회는 `search.json`을 이용해 클라이언트에서 처리한다.

---

# 업데이트

명령:

```bash
ntindex update
```

동작:

```text
crawl
↓
build
```

---

# 검색

메인 페이지에서 우선 버튼으로 게임을 선택, 해당하는 html 파일로 이동

사용자 입력:

```text
[캐릭터 검색창:텍스트 입력]
[CHAR1]
[CHAR2]

as

[캐릭터 검색창:텍스트 입력]
[CHAR1]

in [GAME]
```

예:

```text
[캐릭터 검색창:텍스트 입력]
Furina

as

[캐릭터 검색창:텍스트 입력]
Nahida

in Genshin
```

(검색할 때 사용하는 캐릭터 이름은 각각 없을 수도, 여러 개일 수도 있다. 없는 경우 조건이 없는 것으로 취급해 해당 부분을 모든 캐릭터처럼 취급하고, 여러 개인 경우 각 캐릭터들에 대한 영상을 모두 조회한다.)

검색 절차:

1. game 이름 검색
2. character(source) 이름 검색
3. character(target) 이름 검색
4. 매칭된 id 집합 생성
5. videos 검색

해당 검색은 JS로 이루어진다. SQL은 정적 사이트에서 사용할 수 없기 때문.

---

# 병합

## 게임 병합

명령:

```bash
ntindex merge game <old_id> <new_id>
```

예:

```bash
ntindex merge game 12 3
```

동작:

```sql
UPDATE characters
SET game_id = 3
WHERE game_id = 12;

UPDATE videos
SET game_id = 3
WHERE game_id = 12;

UPDATE games
SET id = 3
WHERE id = 12;
```
(games 테이블에서는, 다른 이름이 같은 id를 가리키게 함.)

---

## 캐릭터 병합

명령:

```bash
ntindex merge character <old_id> <new_id>
```

예:

```bash
ntindex merge character 51 8
```

동작:

```sql
UPDATE videos
SET source_id = 8
WHERE source_id = 51;

UPDATE videos
SET target_id = 8
WHERE target_id = 51;

UPDATE characters
SET id = 8
WHERE id = 51;
```
(characters 테이블에서는, 다른 이름이 같은 id를 가리키게 함.)

제약:

```text
old.character.game_id
==
new.character.game_id
```

같은 게임에 속한 캐릭터끼리만 병합 가능.

---

# 설계 원칙

1. SQLite가 유일한 Origin of Truth이다.
2. JSON은 검색 및 렌더링용 산출물이다.
3. HTML은 정적 산출물이다.
4. 크롤링 시에는 최대한 관대하게 등록한다.
5. 잘못된 매핑은 수동 병합으로 정리한다.
6. 자동 추론보다 데이터 무결성을 우선한다.
7. 검색보다 등록 정확성을 우선한다.
8. 운영 서버 없이 정적 호스팅을 목표로 한다.
