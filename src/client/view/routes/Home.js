import styled from "styled-components";

import { LinkCardsView } from "../pages/LinkCardsView";
import { LinkCardsJs as CardContents } from "../../components/component/LinkCardsJs";
// import { SvgImg } from "../components/component/pages/SvgImgJs";
// import { Calendar } from "../components/component/pages/CalendarJs";


export const Body = styled.div `
  display: flex;
  width: 100%;
  flex-wrap: wrap;
`;

export const Home = () => {
  return (
    <>
      <Body>
        <div style={{display: 'flex', width: '100%', height: '8em', flexWrap: 'wrap',alignItems: 'center', justifyContent: 'center'}}>
          <p style={{fontSize: '2em'}}>프론트엔드 개발자를 꿈꾸는 이서안의 포트폴리오입니다.</p>
          <p>프로젝트에 대한 자세한 설명은 About 메뉴에 기록해 두었습니다.</p>
        </div>
        
        <CardContents />
      </Body>
    </>
  )
}

export default Home;