import { Link } from "react-router-dom";

// import { Container, Wrapper, Text } from "../../view/layout/FooterView";
import styled from "styled-components";


export const Container = styled.footer `
  width: ${props => (props.scrl ? 'calc(100% - 24px)' : 'calc(100% - 16px)')};
  margin: ${props => (props.scrl ? '8px 16px 8px 8px' : '8px')};
`;

export const Wrapper = styled.div `
  display: flex;
  width: calc(100% - 16px);
  height: 30px;
  padding: 0 8px;
  align-items: center;
  flex-wrap: wrap;
  border-top: 1px solid #bfbfbf;
  overflow-y: hidden;
`;

export const Text = styled.p `
  margin: 0;
  font-size: 0.8em;
  color: #333;
  white-space: pre;

  & > a {
    text-decoration: none;
    color: #333;
  }
`;

export const Mail = () => {
  const naver = `${process.env.REACT_APP_PERSONAL_EMAIL_ADDRESS_NAVER}`;
  //const gmail = `${process.env.REACT_APP_PERSONAL_EMAIL_ADDRESS_GMAIL}`;

  // const copyMail = ( address ) => {
  //   return (
  //     <span onClick={async(e) => {
  //       await navigator.clipboard.writeText(address);
  //       alert(`${address} 메일 주소가 클립보드에 복사되었습니다.`);
  //       e.preventDefault();
  //     } } style={{cursor: "pointer"}}>클릭해서 메일 주소 복사하기</span>
  //   )
  // };
  const handleCopy = async (mail) => {
    const string = mail;
    try {
      const permissionStatus = await navigator.permissions.query({ name: "clipboard-write" });
      if (permissionStatus.state === 'granted' || permissionStatus.state === 'prompt') {
        // 클립보드 권한이 이미 허용되어 있음
        // console.log('클립보드 권한이 이미 허용되어 있습니다.');
        await navigator.clipboard.writeText(string);
        alert(`${string} 메일 주소가 클립보드에 복사되었습니다.`);
      } else {
        alert(`권한이 없어 클립보드로 복사할 수 없습니다.
메일 주소는 ${string} 입니다.`);
      }
      
    } catch (error) {
      console.error('Fail to load Cpilpboard API');
      alert(`사파리를 사용중이신가요? 클립보드로 복사할 수 없습니다.
메일 주소는 ${string} 입니다.`);
    }
  }

  const copyMail = () => {
    return (
      <span onClick={(event) => {
        event.preventDefault();
        handleCopy(naver);
      } } style={{cursor: "pointer"}}>클릭해서 메일 주소 복사하기</span>
    )
  };

  return copyMail();
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