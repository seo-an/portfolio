import React from 'react';
import * as ReactDOMClient from 'react-dom/client';

import GlobalStyle from './client/components/view/common/GlobalStyle';
import GlobalFonts from './client/components/view/common/GlobalFonts';
import App from './App';


const root = ReactDOMClient.createRoot(document.getElementById('root'));
root.render(
  <>
    <GlobalStyle />
    <GlobalFonts />
    <App />
  </>
);