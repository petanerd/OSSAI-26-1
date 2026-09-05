# GitHub에서 코드 검사 실행하기

`petanerd/OSSAI-26-1` 공개 저장소의 현재 코드로 Ubuntu에서 자동 검사한다.
개인 컴퓨터를 연결하거나 API Key를 등록할 필요가 없다.

## 실행되는 검사

1. Python 3.12와 `uv.lock`에 고정된 의존성을 설치한다.
2. Ruff로 코드 작성 규칙을 검사한다.
3. pytest로 전체 회귀 테스트를 실행한다.
4. 저장된 답 한 건을 고정 규칙으로 채점하는 설명 명령을 실행한다.

모델 API 요청은 0회다. 의존성 설치에는 인터넷을 사용하지만 `.env`, 개인 입력 데이터나
기존 실제 API 응답은 업로드하지 않는다. 저장 답의 채점 실패는 설명용이며, 명령 자체의
오류와 구분한다. 이 검사는 실제 모델 품질 평가를 대신하지 않는다.

## GitHub 화면에서 확인하기

- PR을 만들거나 수정하면 **Actions → PR offline evaluation → test-only**가 실행된다.
- `main`과 최초 확인용 `work/github-actions` 브랜치의 push에도 실행된다.
- workflow가 기본 브랜치에 병합된 뒤에는 같은 Actions 화면의 **Run workflow** 버튼으로
  수동 실행할 수 있다.
- 실행 URL·commit SHA와 각 단계의 결과를 확인한다. 실패한 단계는 로그를 열어 원인을 읽는다.

현재 공개 `main`은 Week 4까지다. Week 5·6의 미공개 작업 코드, Phoenix 검사, nightly·weekly
실제 NIM 호출은 이 변경에 포함하지 않는다. 해당 코드 공개와 실제 호출 승인을 마친 뒤
별도 연결한다. AI가 PR을 자동 병합하거나 수업 release를 승인하지 않는다.
