export const PapagoTransForm = ( func ) => {

  return (
		<>
      <div>
        <h2>파파고 번역 API</h2>
				<p>영문 번역기</p>

        <div className="sub">
          <form onSubmit={func.props}>
            <input type="text" id="papago" placeholder="한국어 문장을 입력하세요."/>
						<button style={{display: "inline-flex"}} type="submit">번역</button>
					</form>
				</div>
			</div>
		</>
	);
}