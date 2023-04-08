// 사용안함
export const RegistrationInfo = () => {
  // http://apis.data.go.kr/1543061/animalInfoSrvc/animalInfo
  // api: 동물등록번호 혹은 RFID 코드 + 소유자 성명 또는 생년월일 입력하여 요청 >> 반려동물 이름, 성별, 품종, 중성화 여부, 담당기관 등의 정보 제공
  
  // 등록번호 (15자리 숫자)
  // 소유자 이름, 연락처 (휴대폰)
  // 주소
  // 동물명
  // 품종
  // 모색
  // 생년월일
  // 성별
  // 중성화 여부
  const pet = [
    { id: "",  belongsTo: "owner login id", nameTag: "pet's unique id", serialNum: "abcab12", name: "치약", age: "", sex: "Male", birthday: "2022/10/9", desexing: "N", officialRegistNum: "", sns: "Y/N"}
  ];
  const petDetail = [
    { id: "", serialNum: "abcab12", family: "Parrot", species: "블루헤드 피어니스", color: "", feature: "특징", twitter: "", instagram: "", facebook: "", youtube: "", tiktok: "", blog: "", }
  ];
  //sns
  const owner = [
    { id: "", ownerOf: "", serialNum: "pp05ab", name: "", birthday: "", contact: "not null, T/F (isEntered?)", emergency: "T/F (isEmergency?)"}
  ];

  const ownerDetail = [
    { id: "", serialNum: "pp05ab", phone: "", email: "", kakao: "", line: "", skype: "", discord: "", slack: "", wechat: "", telegram: "", }
  ];
  // contact가 true이면 phone, email, kakao, line, skype, discord, slack, wechat, telegram 등 정보 입력 받음 (추가 형식으로 여러개 등록 가능)
  // emergency 상황에서 open할 긴급 연락처 추가

  return (
    <>
    </>
  )

}