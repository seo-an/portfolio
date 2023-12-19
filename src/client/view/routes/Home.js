import styled from 'styled-components';

import { HomeCardsJs as CardContents } from '../../components/component/HomeCardsJs.js';


export const Body = styled.div `
  display: flex;
  width: 100%;
  flex-wrap: wrap;
  background-color: ${props => props.backgroundColor || 'white'};
`;


export const Home = () => {
  // const backgroundColor = 'black';
  return (
    <>
      <Body>
        <div style={{display: 'block', width: '100%', height: '8em', textAlign: 'center'}}>
          <p style={{fontSize: '2em', lineHeight: '3em'}}>프론트엔드 개발자를 꿈꾸는 이서안의 포트폴리오입니다.</p>
          <p>프로젝트에 대한 자세한 설명은 About 메뉴에 기록해 두었습니다.</p>
          <p style={{fontSize: '0.8em'}}>기능 위주로 구현하여 디자인이 다소 미흡할 수 있습니다.</p>
        </div>
        
        <CardContents />
      </Body>
    </>
  )
}

export default Home;