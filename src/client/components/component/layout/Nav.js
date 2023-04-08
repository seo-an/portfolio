import SetURL from "../../data/SetURL";

import { Wrapper } from "../../view/layout/NavView";

const Nav = ({ nowScroll }) => {
  return (
    (nowScroll ? (
      <>
        <Wrapper scrl>
          <SetURL />
        </Wrapper>
      </>
    ) : (
      <>
        <Wrapper>
          <SetURL />
        </Wrapper>
      </>
    ))
  )
}

export default Nav;