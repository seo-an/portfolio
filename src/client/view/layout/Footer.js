import { Link } from 'react-router-dom';

import styled from 'styled-components';

import { copyToClipboard } from '../../../utils/copyToClipboard.js';


export const Container = styled.footer `
  width: ${props => (props.scrl ? 'calc(100% - 24px)' : 'calc(100% - 16px)')};
  margin: ${props => (props.scrl ? '8px 16px 8px 8px' : '8px')};
  grid-row: 3;
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


const handleCopy = (event) => {
  event.preventDefault();

  const myNaver = `${process.env.REACT_APP_PERSONAL_EMAIL_ADDRESS_NAVER}`;
  const myGmail = `${process.env.REACT_APP_PERSONAL_EMAIL_ADDRESS_GMAIL}`;

  const toCopy = {
    browserEnv: navigator.userAgent,
    data: myNaver || myGmail,
    errorMessage: `메일 주소는 ${myNaver} 입니다.`
  }

  copyToClipboard(toCopy);
  return event.stopPropagation();
};


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
              }}>Github 바로가기</Link>  |  <Link to={`https://seo-an.notion.site/seo-an/Seoan-Lee-b28a4bab30f84e0da7c04284a747ea8a`} target={'_blank'} onClick={(event) => {
                event.preventDefault();
                window.open(`https://seo-an.notion.site/seo-an/Seoan-Lee-b28a4bab30f84e0da7c04284a747ea8a`);
              }}>Notion 바로가기</Link>  |  Mail: <span id='copyMail' onClick={handleCopy} style={{cursor: "pointer"}}>클릭해서 메일 주소 복사하기</span>  |  오늘도 행복한 하루 보내세요 :D
            </Text>
            {/* <div>
              이서안  Seoan Lee  |  <Link to={`https://github.com/seo-an`} target={'_blank'} onClick={(event) => {
                event.preventDefault();
                window.open(`https://github.com/seo-an`);
              }}>Github 바로가기</Link>  |  Mail: <span id='copyMail' onClick={handleCopy} style={{cursor: "pointer"}}>클릭해서 메일 주소 복사하기</span>  |  오늘도 행복한 하루 보내세요 :D
            </div> */}
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
              }}>Github 바로가기</Link>  |  <Link to={`https://seo-an.notion.site/seo-an/Seoan-Lee-b28a4bab30f84e0da7c04284a747ea8a`} target={'_blank'} onClick={(event) => {
                event.preventDefault();
                window.open(`https://seo-an.notion.site/seo-an/Seoan-Lee-b28a4bab30f84e0da7c04284a747ea8a`);
              }}>Notion 바로가기</Link>  |  Mail: <span id='copyMail' onClick={handleCopy} style={{cursor: "pointer"}}>클릭해서 메일 주소 복사하기</span>  |  오늘도 행복한 하루 보내세요 :D
            </Text>
          </Wrapper>
        </Container>
      </>
    )
  }
}