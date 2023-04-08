import { Link } from "react-router-dom";

import { Container, Wrapper, Text } from "../../view/layout/FooterView";

// export const Mail = () => {
//   const mail = `seo-an_@naver.com`;
//   return (
//     <span onClick={async(e) => {
//       await navigator.clipboard.writeText(mail);
//       alert(`${mail}이 클립보드에 복사되었습니다.`);
//       e.preventDefault();
//     } }>{mail}</span>
//   )
// }

export const Mail = () => {
  const naver = `seo-an_@naver.com`;
  const gmail = `jay2019lee@gmail.com`;

  const copyMail = ( address ) => {
    return (
      <span onClick={async(e) => {
        await navigator.clipboard.writeText(address);
        alert(`${address} 메일 주소가 클립보드에 복사되었습니다.`);
        e.preventDefault();
      } }>클릭해서 메일 주소 복사하기</span>
    )
  };

  return copyMail(naver);
}

export const Footer = ({ nowScroll }) => {
  if( nowScroll ) {
    return (
      <>
        <Container scrl>
          <Wrapper>
            <Text>
              이서안  Seoan Lee  |  <Link to={`https://github.com/seo-an`} target={'_blank'} onClick={(event) => {
                event.preventDefault();
                window.open(`https://github.com/seo-an`);
              }}>Github 바로가기</Link>  |  Mail: <Mail />  |  오늘도 행복한 하루 보내세요 :D
            </Text>
          </Wrapper>
        </Container>
      </>
    )
  } else {
    return (
      <>
        <Container>
          <Wrapper>
            <Text>
              이서안  Seoan Lee  |  <Link to={`https://github.com/seo-an`} target={'_blank'} onClick={(event) => {
                event.preventDefault();
                window.open(`https://github.com/seo-an`);
              }}>Github 바로가기</Link>  |  Mail: <Mail />  |  오늘도 행복한 하루 보내세요 :D
            </Text>
          </Wrapper>
        </Container>
      </>
    )
  }
}