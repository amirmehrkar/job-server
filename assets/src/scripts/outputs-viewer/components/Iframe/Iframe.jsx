import PropTypes from "prop-types";
import React, { useLayoutEffect, useState } from "react";
import { useFiles } from "../../context/FilesProvider";
import useWindowSize from "../../hooks/use-window-size";

function Iframe({ data }) {
  const {
    state: { file },
  } = useFiles();
  const windowSize = useWindowSize();
  const [frameHeight, setFrameHeight] = useState(0);
  const id = encodeURIComponent(file.url).replace(/\W/g, "");

  useLayoutEffect(() => {
    if (document.getElementById(id)) {
      if (window.innerWidth > 991) {
        setFrameHeight(
          Math.round(
            window.innerHeight -
              document.getElementById(id).getBoundingClientRect().top -
              17 - // Magic number for scroll bar height
              40 // 2rem
          )
        );
      } else {
        setFrameHeight(1000);
      }
    }
  }, [windowSize, id]);

  return (
    <iframe
      frameBorder="0"
      height={frameHeight}
      id={id}
      src={file.url}
      srcDoc={data}
      title={file.name}
      width="100%"
    />
  );
}

export default Iframe;

Iframe.propTypes = {
  data: PropTypes.string.isRequired,
};
