import { BrowserRouter, Route, Routes } from "react-router-dom";

import Layout from "./client/view/layout/Layout";
import Home from "./client/view/routes/Home";
import OpenApiPage from "./client/view/routes/OpenApiPage";
import RestApiPage from "./client/view/routes/RestApiPage";
import About from "./client/view/routes/About";
import { DevTestView } from "./_dev_test/DevTestView";

import { Calendar } from "./client/components/component/CalendarJs";
import { SvgImg } from "./client/components/component/SvgImgJs";
import { ModalExamplePageView } from "./client/view/pages/ModalExamplePageView";
import { WindowPopupExamplePageView } from "./client/view/pages/WindowPopupExamplePageView";
import { PopupView } from "./client/view/pages/PopupView";

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
            <Route path="/calendar" element={<Calendar />}></Route>
            <Route path="/svg-component" element={<SvgImg />}></Route>
            <Route path="/modal" element={<ModalExamplePageView />}></Route>
            <Route path="/window-popup" element={<WindowPopupExamplePageView />}></Route>
          </Route>

          {/* 그 외 라우팅 페이지 */}
          <Route path="/popup-view" element={<PopupView />}></Route>

          {/* 에러 및 테스트 */}
          <Route path="*" element={<h1>Error 404</h1>}></Route>
        </Routes>
      </BrowserRouter>
    </>
  );
}