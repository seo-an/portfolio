import { createGlobalStyle } from "styled-components";

const fonts = () => {
  const family = 'seoanCocktail';
  const fontPath = '/fonts/';
  const fontFormat = ['ttf', 'woff', 'opentype', 'woff2', 'embedded-opentype'];
  const unicodeGroup = ['ko_KR', 'en_US', 'ja_JP', 'others'];

  const fontList = 
    {
      ko_KR: [
        {
          style: 'normal', 
          weight: 200, 
          file: 'LINESeedKR-Th', 
          unicode: 'U+1100-U+11FF, U+AC00-U+D7A3, U+3130-U+318F'
        },
        {
          style: 'normal', 
          weight: 400, 
          file: 'LINESeedKR-Rg', 
          unicode: 'U+1100-U+11FF, U+AC00-U+D7A3, U+3130-U+318F'
        },
        {
          style: 'normal', 
          weight: 700, 
          file: 'LINESeedKR-Bd', 
          unicode: 'U+1100-U+11FF, U+AC00-U+D7A3, U+3130-U+318F'
        }
      ],

      en_US: [
        {
          style: 'normal', 
          weight: 200, 
          file: 'LINESeedSans_W_Th', 
          unicode: 'U+0041-U+005A, U+0061-U+007A'
        },
        {
          style: 'normal', 
          weight: 400, 
          file: 'LINESeedSans_W_Rg', 
          unicode: 'U+0041-U+005A, U+0061-U+007A'
        },
        {
          style: 'normal', 
          weight: 700, 
          file: 'LINESeedSans_W_Bd', 
          unicode: 'U+0041-U+005A, U+0061-U+007A'
        },
        {
          style: 'normal', 
          weight: 800, 
          file: 'LINESeedSans_W_He', 
          unicode: 'U+0041-U+005A, U+0061-U+007A'
        },
        {
          style: 'normal', 
          weight: 900, 
          file: 'LINESeedSans_W_XBd', 
          unicode: 'U+0041-U+005A, U+0061-U+007A'
        }
      ],

      ja_JP: [
        {
          style: 'normal', 
          weight: 200, 
          file: 'LINESeedJP_OTF_Th', 
          unicode: 'U+30A0-U+30FF, U+3040-U+309F, U+4E00-U+9FFF, U+3000-U+303F'
        },
        {
          style: 'normal', 
          weight: 400, 
          file: 'LINESeedJP_OTF_Rg', 
          unicode: 'U+30A0-U+30FF, U+3040-U+309F, U+4E00-U+9FFF, U+3000-U+303F'
        },
        {
          style: 'normal', 
          weight: 700, 
          file: 'LINESeedJP_OTF_Bd', 
          unicode: 'U+30A0-U+30FF, U+3040-U+309F, U+4E00-U+9FFF, U+3000-U+303F'
        },
        {
          style: 'normal', 
          weight: 800, 
          file: 'LINESeedJP_OTF_Eb', 
          unicode: 'U+30A0-U+30FF, U+3040-U+309F, U+4E00-U+9FFF, U+3000-U+303F'
        }
      ],
      
      others: [
        {
          style: 'normal', 
          weight: 200, 
          file: 'KoPubWorld Dotum Light', 
        },
        {
          style: 'normal', 
          weight: 400, 
          file: 'KoPubWorld Dotum Medium', 
        },
        {
          style: 'normal', 
          weight: 700, 
          file: 'KoPubWorld Dotum Bold', 
        }
      ]
    }
  ;


  let result = '';

  for (let i = 0;i < unicodeGroup.length;i++) {
    for (let j = 0;j < fontList[unicodeGroup[i]].length;j++) {
      const cssSetting = 
      `
        @font-face {
          font-family: '${family}';
          font-style: '${fontList[unicodeGroup[i]][j].style}';
          font-weight: ${fontList[unicodeGroup[i]][j].weight};
          src: local('${family}'), url('${fontPath}${fontList[unicodeGroup[i]][j].file}.${fontFormat[3]}') format('${fontFormat[3]}');
          unicode-range: ${fontList[unicodeGroup[i]][j].unicode};
        }
      `;

      result += cssSetting;
    }
  }

  return result;
}


const GlobalFonts = createGlobalStyle `
  ${fonts()}
`;


export default GlobalFonts;

// seoanCocktail
// LineSeed
// KoPubWorld


// 한글 (Hangul): U+1100-U+11FF, U+AC00-U+D7A3, U+3130-U+318F
// 영어 (English): U+0041-U+005A, U+0061-U+007A
// 일본어 (Japanese): U+30A0-U+30FF, U+3040-U+309F, U+4E00-U+9FFF

// 한글 자모음: U+1100-U+11FF
// 한글 음절: U+AC00-U+D7A3
// 한글 자모 자모음: U+3130-U+318F

// 영어 대문자: U+0041-U+005A
// 영어 소문자: U+0061-U+007A

// 가타카나 (가타카나): U+30A0-U+30FF
// 히라가나 (ひらがな): U+3040-U+309F
// 칸지 (漢字): U+4E00-U+9FFF

// 아라비아 숫자 (0-9): U+0030-U+0039
// 일본어 숫자: U+3000-U+303F
// 중국어 숫자: U+4E00-U+9FFF
// 르샤프르 숫자 (유럽 숫자, 프랑스어): U+1040-U+1049
// 불가리아 숫자: U+16A0-U+16FF
// 아라비아 숫자 확장 (프라키트, 야나니 등): U+0660-U+0669