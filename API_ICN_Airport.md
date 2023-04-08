# OPEN API 명세
## 인천공항공사 기상정보
###### Incheon International Airport Corporaion_Weather Information

- 서비스 URL (운영): http://apis.data.go.kr/B551177/StatusOfPassengerWorldWeatherInfo
- 서비스 WADL (운영): http://apis.data.go.kr/B551177/StatusOfPassengerWorldWeatherInfo?_wadl

- 적용 기술 수준: 인터페이스 (REST), 교환 데이터 표준 (XML, JSON)
- 메시지 교환 유형: Request-Response
- 서비스 제공자: 박건규/ 스마트정보처 스마트기획팀/ 032-741-7280/ assembly@airport.kr
- 데이터 갱신 주기: 3분

### API 요청 메세지 명세
#### 오퍼레이션 목록


| 항목명(영문) | 항목명(국문) | 항목크기 | 항목구분 | 샘플데이터 | 항목설명 | json structure |
|:---:|:---:|:---:|:---:|:---:|:---|:---:|
| `airline` | 항공사 | 8 | 0 | 이란항공 | 항공사 국문명. 별첨 항공사 코드를 이용하여 해당 공항의 여객편만 조회 | `body.item` |
| `flightId` | 편명 | 4 | 0 | LA8425 | 항공 편명 | `body.item` |
| `scheduleDateTime` | 예정시간 | 4 | 0 | 0500 | 도착예정시간 HHMM | `body.item` |
| `estimatedDateTime` | 변경시간 | 4 | 0 | 0500 | 도착변경시간 HHMM | `body.item` |
| `airport` | 출발공항 | 10 | 0 | 로스앤젤레스 | 출발 공항 한글명 | `body.item` |
| `gatenumber` | 탑승구 | 1 | 0 | - | 탑승구 번호 | `body.item` |
| `carousel` | 수하물수취대 | 4 | 0 | - | 수하물 수취대 번호 | `body.item` |
| `exitnumber` | 출구 | 4 | 0 | - | 출구 번호 | `body.item` |
| `remark` | 현황 | 8 | 0 | - | 운항상태(출발,결항,지연,탑승중,마감예정,탑승마감,탑승준비) | `body.item` |
| `airportCode` | 공항코드 | 8 | 0 | LAX | 출발 공항 코드(IATA) 별첨 공항코드를 이용하여 해당 공항의 여객편만 조회 | `body.item` |
| `yoil` | 날씨표출 요일 | 4 | 0 | 수 | 출발도시 요일 | `body.item` |
| `himidity` | 습도 | 4 | 0 | 81 | 출발도시 습도(%) | `body.item` |
| `wimage` | 날씨 이미지 경로 | 80 | 0 | - | 날씨 이미지 url 경로 | `body.item` |
| `wind` | 풍속 | 4 | 0 | 2 | 출발도시 풍속(m/s) | `body.item` |
| `temp` | 관측 기온 | 4 | 0 | 17 | 출발도시 관측 기온(℃) | `body.item` |
| `senstemp` | 체감 온도 | 4 | 0 | 13 | 출발도시 체감 온도(℃) | `body.item` |
| `terminalid` | 터미널 구분 | 4 | 0 | P03 | P01: 제1 터미널 <br/> P02: 탑승동 <br/> P03: 제2 터미널 <br/> C01 : 화물터미널 남측 <br/> C02 : 화물터미널 북측 <br/> C03 : 화물터미널 남측 | `body.item` |
| `resultCode` | 결과코드 | 2 | 1 | 00 | 결과코드 | `header` |
| `resultMsg` | 결과메시지 | 50 | 1 | NORMALSERVICE | 결과메시지 | `header` |
| `numOfRows` | 데이터 행 | 10 | 1 | 10 | 데이터 행 | `body` |
| `pageNo` | 데이터 표출 페이지 | 1 | 1 | 1 | 데이터 표출 페이지 | `body` |
| `totalCount` | 데이터 항목 수 | 4 | 1 | 71 | 데이터 항목 수 | `body` |

* ※ 항목구분 : 필수(1), 옵션(0), 1건 이상 복수건(1..n), 0건 또는 복수건(0..n)