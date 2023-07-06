# portfolio
<br>
안녕하세요.<br>
<br>
이서안의 포트폴리오 페이지 입니다.<br>
<br>
main 브랜치는 seo-an.com 에서 호스팅되고 있습니다.<br>
<br>
현재 개발중인 기능은 dev 브랜치에 있습니다.<br>
<br>
-*<br>
<br>
이 프로젝트는 Nginx, Node.js(express), ReactJs로 이루어졌습니다.<br>
<br>
<br>
<프로젝트 폴더 구성><br>
 ┣─  src<br>
&emsp;┣─ client<br>
&emsp;&emsp;┣─ components<br>
&emsp;&emsp;&emsp;┣─ component<br>
&emsp;&emsp;&emsp;&emsp;┣─ layout<br>
&emsp;&emsp;&emsp;&emsp;┣─ pages<br>
&emsp;&emsp;&emsp;┣─ data<br>
&emsp;&emsp;&emsp;┣─ js<br>
&emsp;&emsp;&emsp;┣─ view<br>
&emsp;&emsp;&emsp;&emsp;┣─ common<br>
&emsp;&emsp;&emsp;&emsp;┣─ icon/svg<br>
&emsp;&emsp;&emsp;&emsp;┣─ image<br>
&emsp;&emsp;&emsp;&emsp;┣─ layout<br>
&emsp;&emsp;&emsp;&emsp;┣─ pages<br>
&emsp;&emsp;┣─ routes<br>
<br>
<br>
<br>
🤖 routes 폴더에는 App의 상단 메뉴와 대응되는 리액트 컴포넌트들이 위치하고 있습니다. 해당 페이지에서 보여주고 싶은 내용은 모두 이 리액트 컴포넌트들을 통해 노출됩니다. 이 폴더의 파일들은 App.js에서 라우팅 됩니다.<br>
<br>
🤖components 폴더에는 페이지 내용과 관련된 리액트 컴포넌트, 자바스크립트 파일이 위치해 있습니다.<br>
<br>
└🤖 페이지 내용을 보여주기 위해 필요한 자바스크립트와 스타일 css를 각각 component와 view 폴더 하위의 pages 폴더에 나누어 구성하였습니다. 두 개의 파일은 페이지 내용을 대표할 수 있는 이름+역할로 명명되어 있습니다(예를 들어, ExampleJs.js 와 ExampleView.js). 하나의 내용을 보여주는 파일을 굳이 두 개로 나눈 이유는 ‘자바스크립트를 수정하는 사람과 디자인을 수정하는 사람이 다를 경우 파일 구조를 분리해서 구성할 수 있을까’에 대한 궁금함을 가지고 있었기 때문입니다. 이를 직접 구현해봄으로써 한 파일 내에 자바스크립트와 스타일 css를 구성하였을 때와 차이점, 각각의 장단점에 대해 더 잘 알 수 있게 되었습니다.<br>
<br>
└🤖js 폴더에는 두 개 이상의 컴포넌트에서 쓰이는 함수를 별도의 자바스크립트 파일, 리액트 컴포넌트로 작성하여 두었습니다.<br>
<br>
└🤖data 폴더에는 데이터베이스에 저장될 필요는 없지만 사전에 가지고 있어야 하는 정보에 대한 파일이 위치해 있습니다.<br>
<br>
<br>

## 방문해주셔서 감사합니다.
