import React from 'react';
import * as ReactDOMClient from 'react-dom/client';

import GlobalStyle from './styles/global/GlobalStyle';
import GlobalFonts from './styles/global/GlobalFonts';
import App from './App';


const root = ReactDOMClient.createRoot(document.getElementById('root'));
root.render(
  <>
    <GlobalStyle />
    <GlobalFonts />
    <App />
  </>
);