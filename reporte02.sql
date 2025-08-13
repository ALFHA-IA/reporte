--
-- Estructura de tabla para la tabla `clientes`
--

CREATE TABLE clientes (
  id_cliente SERIAL PRIMARY KEY,
  doc_cliente VARCHAR(50),
  cliente VARCHAR(255) NOT NULL,
  telefono VARCHAR(50)
);

--
-- Estructura de tabla para la tabla `productos`
--

CREATE TABLE productos (
  id_producto SERIAL PRIMARY KEY,
  producto VARCHAR(255) NOT NULL,
  precio DECIMAL(10,2) NOT NULL
);

--
-- Estructura de tabla para la tabla `ventas`
--

CREATE TABLE ventas (
  id_venta SERIAL PRIMARY KEY,
  id_cliente INT,
  fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  total DECIMAL(10,2) NOT NULL
);

--
-- Estructura de tabla para la tabla `detalle_venta`
--

CREATE TABLE detalle_venta (
  id_detalle SERIAL PRIMARY KEY,
  id_venta INT NOT NULL,
  id_producto INT NOT NULL,
  cantidad INT NOT NULL,
  precio_unitario DECIMAL(10,2) NOT NULL
);

--
-- Indices de la tabla `ventas`
--

ALTER TABLE ventas
  ADD CONSTRAINT fk_cliente
  FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente);

--
-- Filtros para la tabla `detalle_venta`
--

ALTER TABLE detalle_venta
  ADD CONSTRAINT fk_detalle_venta_venta
  FOREIGN KEY (id_venta) REFERENCES ventas(id_venta);

ALTER TABLE detalle_venta
  ADD CONSTRAINT fk_detalle_venta_producto
  FOREIGN KEY (id_producto) REFERENCES productos(id_producto);

