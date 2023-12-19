import { BrowserRouter, Route, Routes } from 'react-router-dom';

import Layout from './client/view/layout/Layout.js';
import Home from './client/view/routes/Home.js';
import OpenApiPage from './client/view/routes/OpenApiPage.js';
import RestApiPage from './client/view/routes/RestApiPage.js';
import About from './client/view/routes/About.js';
// import { DevTestView } from './_dev_test/DevTestView.js';

// import { CalendarReactJsPowered } from './client/components/component/CalendarReactJsPowered.js';
import { CalendarView } from './client/view/pages/CalendarView.js';
import { SvgImg } from './client/components/component/SvgImgJs.js';
import { FlightApiJs } from './client/components/component/FlightApiJs.js';
import { ModalExamplePageView } from './client/view/pages/ModalExamplePageView.js';
import { WindowPopupExamplePageView } from './client/view/pages/WindowPopupExamplePageView.js';
import { DateRangeExamplePageView } from './client/view/pages/DateRangeExamplePageView.js';

import { PopupView } from './client/view/pages/PopupView.js';

export default function App() {
  const ready = process.env.REACT_APP_IS_READY;

  return (
    <>
      <BrowserRouter basename="/">
        <Routes>

          <Route exact path="/" element={<Layout />}>
            {/* 상단 메뉴 */}
            <Route index element={<Home />}></Route>
            <Route path="/home" element={<Home />}></Route>
            <Route path="/handle-open-api" element={<OpenApiPage />}></Route>
            <Route path="/handle-rest-api" element={<RestApiPage />}></Route>
            <Route path="/about" element={<About />}></Route>
            {/* 카드 메뉴 */}
            <Route path="/calendar" element={<CalendarView />}></Route>
            <Route path="/svg-component" element={<SvgImg />}></Route>
            <Route path="/api-datas-go-kr" element={<FlightApiJs />}></Route>
            <Route path="/modal" element={<ModalExamplePageView />}></Route>
            <Route path="/window-popup" element={<WindowPopupExamplePageView />}></Route>
            {/* <Route path="/date-range-selection" element={<DateRangeExamplePageView />}></Route> */}
          </Route>

          {/* 그 외 라우팅 페이지 */}
          <Route path="/popup-view" element={<PopupView />}></Route>

          {/* 에러 및 테스트 */}
          <Route path="*" element={<h1>Error 404</h1>}></Route>
          {/* <Route path="/dev-test" element={<DevTestView />}></Route> */}
          
        </Routes>
      </BrowserRouter>
    </>
  );
}