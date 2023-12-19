import styled from 'styled-components';

export const Container = styled.div `
  display: flex;
  width: calc(100% - 64px);
  min-height: calc(100% - 96px);
  padding: 48px 32px;
  flex-wrap: wrap;
`;

export const Title = styled.div `
  display: flex;
  width: 100%;
  height: 100%;
  
  
  & span {
    font-size: 2em;
    line-height: 4em;
  }
`;

export const Paragraph = styled.div `
  display: flex;
  width: 100%;
  height: 100%;
  margin: 8px 0;
  flex-wrap: wrap;

  & p {
    width: 100%;
    margin: 0;
    padding: 0;
    font-size: 1.2em;
    line-height: 2em;
  }
`;

export const Subtitle = styled.div `
  display: flex;
  width: 100%;
  height: 100%;
  
  & span {
    font-size: 1.2em;
    line-height: 2.4em;
  }
`;


const About = () => {
  return (
    <>
      <Container>
        {/* <Title><span>프론트엔드 개발자를 꿈꾸는 이서안의 포트폴리오입니다.</span></Title> */}
        <Title><span>Project,</span></Title>
        <Paragraph>
          <Subtitle><span>이 프로젝트는요,</span></Subtitle>
          <p>Node.js와 React로 이루어졌습니다. 
            Node.js는 npm으로 통용되는 package manager를 제공합니다. 
            npm이 제공하는 package.json으로 쉽게 다양한 패키지와 모듈을 관리하고 프로젝트에 적용할 수 있습니다. 
            또한 간단한 커맨드 스크립트를 사전에 작성해두어 npm run 명령어로 쉽게 build 하고, 구동해 볼 수 있다는 점. 
            그리고 React 서버와 Node.js 서버를 동시에 띄울 수 있다는 점 등이 실제 배포를 염두에 두는 React 프로젝트를 관리하기에 적합하다고 판단하여 Node.js를 선택했습니다. 
            물론 Node.js가 커뮤니티에서 정보를 얻기 용이하고, 다양한 온라인 강의를 접할 수 있는 등 진입 장벽이 높지 않은 것도 선택에 영향을 주었습니다.</p>
        </Paragraph>
        <Paragraph>
          <p>React 역시 커뮤니티가 활발하고 다양한 확장 라이브러리를 제공하고 있습니다. 또한, React는 싱글페이지 구성 프로젝트에 사용됩니다. 
            저의 프로젝트는 단순한 구조를 가지고 있고 정보의 양이 많지 않습니다. 이러한 이유로 React는 혼자서 진행하는 프로젝트에 적용하기 알맞았습니다. 
            저는 CSS와 같은 스타일 요소와 스크립트를 분리하여 관리할 수 있는 프로젝트를 만들어보고 싶었습니다. 
            React에서는 JSX를 컴포넌트에 담아 페이지에 넣고 빼는 것이 자유롭습니다. 컴포넌트와 컴포넌트의 연결도 자유로운 편이기 때문에 스크립트와 JSX를 분리하여 개별 컴포넌트로 작성한 후 한 페이지에 보여주는 것도 가능합니다. 
            React의 styled-components 라이브러리는 스타일과 관련된 요소들도 개별 컴포넌트로 작동하게 만드는 것을 가능하게 해주었습니다. 제가 구현하고자 하는 구조에 React가 가장 적합다고 생각하였기 때문에 React를 선택하였습니다. </p>
        </Paragraph>
        <Paragraph>
          <p>프로젝트 구조가 MVC;Model, View, Controller 패턴 (혹은 VAC 패턴)을 따르도록 도전해 보았습니다. JSX와 CSS는 View에, JS나 기능개발 등은 Action에, Component는 View와 Action 중간에서 서로를 연결하고 추가적으로 필요한 기능을 포함하도록 하였습니다.</p>
          <p>완벽한 MVC 패턴이라고 하기에는 부족함이 있을 수 있겠습니다만, 한 번쯤은 보여지는 페이지에 따라 코드를 구분짓는 것 말고 기능과 역할에 따라 구분하는 프로젝트를 진행해 보고 싶은 욕심이 있었습니다.</p>
        </Paragraph>
        <Paragraph>
          <Subtitle><span>with,</span></Subtitle>
          <p>이 프로젝트는 AWS Lightsail을 통해 호스팅 되고 있습니다.</p>
          <p>이 프로젝트는 정적 파일 배포, Proxy, Reverse Proxy, HTTPS 통신 등을 위해 Nginx를 웹서버로 이용하고 있습니다.</p>
          <p>이 프로젝트는 Lightsail에서 제공하는 MySQL 데이터베이스와 연결되어 있습니다.</p>
          <p>AWS의 Cloud Watch와 AWS Lambda 함수로 5분에 한 번씩 인스턴스의 상태를 점검하여 무중단 배포되도록 조치하였습니다.</p>
        </Paragraph>
        <Paragraph>
          <Subtitle><span>Layout,</span></Subtitle>
          <p>이 프로젝트는 최소 너비와 최대 너비가 제한된 반응형 웹으로, 모바일 페이지를 별도로 지원하지는 않습니다. 
            최소 너비보다 화면이 줄어든다면 좌우 스크롤이 생기고, 최대 너비보다 화면의 너비가 늘어난다면 내용이 담긴 영역이 가운데에 정렬되게 됩니다.</p>
          <p>Layout은 상단에 nav 메뉴바, 중앙에 main 컨텐츠, 하단에 footer를 가지는 전통적인 구조를 따랐습니다.</p>
        </Paragraph>

        <Title><span>Pages</span></Title>
        <Paragraph>
          <Subtitle><span>Home,</span></Subtitle>
          <p>
            Home 화면에서는 제가 구현해 본 기능들을 편안하게 확인하실 수 있도록 카드식으로 나열해 보았습니다. 각 카드를 클릭하시면 해당 내용을 새 창에서 확인하실 수 있습니다.
          </p>
        </Paragraph>
        <Paragraph>
          <Subtitle><span>API 포트폴리오,</span></Subtitle>
          <p>API 포트폴리오 화면에는 Papago Api가 구현되어 있습니다.</p>
          <p>한국어를 영어로 번역할 수 있습니다.</p>
        </Paragraph>
        <Paragraph>
          <Subtitle><span>REST API 포트폴리오,</span></Subtitle>
          <p>REST API 포트폴리오 화면에서는 방명록을 작성하고 삭제할 수 있습니다.</p>
          <p>React.js에서 fetch로 요청을 보내면 Nginx를 타고 백엔드 서버인 Node.js로 보내집니다.</p>
          <p>조회, 작성, 삭제 요청은 Node.js에서 get, post, delete로 처리됩니다.</p>
          <p>작성해주신 방명록은 AWS Lightsail에 연결된 MySQL RDS Database에 저장됩니다.</p>
        </Paragraph>

        <Title><span>마치며,</span></Title>
        <Paragraph>
          <p>한 걸음 더 나아가는 만큼, 한 가지 더 구현하여 적용할 예정이니 생각나실 때 한 번씩 찾아와 주세요!</p>
          <p>감사합니다.</p>
        </Paragraph>
      </Container>
    </>
  )
}

export default About;