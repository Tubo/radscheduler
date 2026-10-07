module OpenApi.Common exposing
    ( encodeStringDate, encodeStringDateTime, toParamStringStringDate, toParamStringStringDateTime
    , decodeStringDate, decodeStringDateTime
    , Nullable(..), Error(..), jsonDecodeAndMap, decodeOptionalField
    , bytesResolverCustom, expectBytesCustom, stringResolverCustom, expectStringCustom, jsonResolverCustom, expectJsonCustom
    )

{-|


## Encoders

@docs encodeStringDate, encodeStringDateTime, toParamStringStringDate, toParamStringStringDateTime


## Decoders

@docs decodeStringDate, decodeStringDateTime


## Common

@docs Nullable, Error, jsonDecodeAndMap, decodeOptionalField


## elm/http

@docs bytesResolverCustom, expectBytesCustom, stringResolverCustom, expectStringCustom, jsonResolverCustom, expectJsonCustom

-}

import Bytes
import Bytes.Decode
import Date
import Dict
import Http
import Json.Decode
import Json.Encode
import Parser.Advanced exposing ((|.), (|=))
import Rfc3339
import Time


encodeStringDate : Date.Date -> Json.Encode.Value
encodeStringDate value =
    Json.Encode.string (Date.toIsoString value)


encodeStringDateTime : Time.Posix -> Json.Encode.Value
encodeStringDateTime value =
    Json.Encode.string
        (Rfc3339.toString
            (Rfc3339.DateTimeOffset
                { instant = value, offset = { hour = 0, minute = 0 } }
            )
        )


toParamStringStringDate : Date.Date -> String
toParamStringStringDate =
    Date.toIsoString


toParamStringStringDateTime : Time.Posix -> String
toParamStringStringDateTime value =
    Rfc3339.toString
        (Rfc3339.DateTimeOffset
            { instant = value, offset = { hour = 0, minute = 0 } }
        )


decodeStringDate : Json.Decode.Decoder Date.Date
decodeStringDate =
    Json.Decode.andThen
        (\andThenUnpack ->
            case Date.fromIsoString andThenUnpack of
                Result.Ok value ->
                    Json.Decode.succeed value

                Result.Err error ->
                    Json.Decode.fail error
        )
        Json.Decode.string


decodeStringDateTime : Json.Decode.Decoder Time.Posix
decodeStringDateTime =
    Json.Decode.andThen
        (\andThenUnpack ->
            case
                Parser.Advanced.run Rfc3339.dateTimeOffsetParser andThenUnpack
            of
                Result.Ok value ->
                    Json.Decode.succeed value.instant

                Result.Err error ->
                    Json.Decode.fail "Invalid RFC-3339 date-time"
        )
        Json.Decode.string


type Nullable value
    = Null
    | Present value


type Error err body
    = BadUrl String
    | Timeout
    | NetworkError
    | KnownBadStatus Int err
    | UnknownBadStatus Http.Metadata body
    | BadErrorBody Http.Metadata body
    | BadBody Http.Metadata body


{-| Chain JSON decoders, when `Json.Decode.map8` isn't enough.
-}
jsonDecodeAndMap :
    Json.Decode.Decoder a
    -> Json.Decode.Decoder (a -> value)
    -> Json.Decode.Decoder value
jsonDecodeAndMap dx df =
    Json.Decode.map2 (|>) dx df


{-| Decode an optional field

    decodeString (decodeOptionalField "x" int) "{ "x": 3 }"
    --> Ok (Just 3)

    decodeString (decodeOptionalField "x" int) "{ "x": true }"
    --> Err ...

    decodeString (decodeOptionalField "x" int) "{ "y": 4 }"
    --> Ok Nothing

-}
decodeOptionalField : String -> Json.Decode.Decoder t -> Json.Decode.Decoder (Maybe t)
decodeOptionalField key fieldDecoder =
    Json.Decode.andThen
        (\andThenUnpack ->
            if andThenUnpack then
                Json.Decode.field
                    key
                    (Json.Decode.oneOf
                        [ Json.Decode.map Just fieldDecoder
                        , Json.Decode.null Nothing
                        ]
                    )

            else
                Json.Decode.succeed Nothing
        )
        (Json.Decode.oneOf
            [ Json.Decode.map
                (\_ -> True)
                (Json.Decode.field key Json.Decode.value)
            , Json.Decode.succeed False
            ]
        )


responseToResult :
    Dict.Dict String (Json.Decode.Decoder err)
    -> (body -> String)
    -> (Http.Metadata -> body -> Result (Error err body) value)
    -> Http.Response body
    -> Result (Error err body) value
responseToResult errorDecoders bodyToString onSuccess response =
    case response of
        Http.BadUrl_ arg_0 ->
            Result.Err (BadUrl arg_0)

        Http.Timeout_ ->
            Result.Err Timeout

        Http.NetworkError_ ->
            Result.Err NetworkError

        Http.BadStatus_ httpMetadata body ->
            case
                Dict.get (String.fromInt httpMetadata.statusCode) errorDecoders
            of
                Nothing ->
                    Result.Err (UnknownBadStatus httpMetadata body)

                Just err ->
                    case Json.Decode.decodeString err (bodyToString body) of
                        Ok res ->
                            Result.Err
                                (KnownBadStatus httpMetadata.statusCode res)

                        Err _ ->
                            Result.Err (BadErrorBody httpMetadata body)

        Http.GoodStatus_ httpMetadata body ->
            onSuccess httpMetadata body


bytesResolverCustom :
    Dict.Dict String (Json.Decode.Decoder err)
    -> Http.Resolver (Error err Bytes.Bytes) Bytes.Bytes
bytesResolverCustom errorDecoders =
    Http.bytesResolver
        (responseToResult
            errorDecoders
            (\body ->
                Maybe.withDefault
                    ""
                    (Bytes.Decode.decode
                        (Bytes.Decode.string (Bytes.width body))
                        body
                    )
            )
            (\metadata body -> Result.Ok body)
        )


expectBytesCustom :
    Dict.Dict String (Json.Decode.Decoder err)
    -> (Result (Error err Bytes.Bytes) Bytes.Bytes -> msg)
    -> Http.Expect msg
expectBytesCustom errorDecoders toMsg =
    Http.expectBytesResponse
        toMsg
        (responseToResult
            errorDecoders
            (\body ->
                Maybe.withDefault
                    ""
                    (Bytes.Decode.decode
                        (Bytes.Decode.string (Bytes.width body))
                        body
                    )
            )
            (\metadata body -> Result.Ok body)
        )


stringResolverCustom :
    Dict.Dict String (Json.Decode.Decoder err)
    -> Http.Resolver (Error err String) String
stringResolverCustom errorDecoders =
    Http.stringResolver
        (responseToResult
            errorDecoders
            Basics.identity
            (\metadata body -> Result.Ok body)
        )


expectStringCustom :
    Dict.Dict String (Json.Decode.Decoder err)
    -> (Result (Error err String) String -> msg)
    -> Http.Expect msg
expectStringCustom errorDecoders toMsg =
    Http.expectStringResponse
        toMsg
        (responseToResult
            errorDecoders
            Basics.identity
            (\metadata body -> Result.Ok body)
        )


jsonResolverCustom :
    Dict.Dict String (Json.Decode.Decoder err)
    -> Json.Decode.Decoder success
    -> Http.Resolver (Error err String) success
jsonResolverCustom errorDecoders successDecoder =
    Http.stringResolver
        (responseToResult
            errorDecoders
            Basics.identity
            (\metadata body ->
                case Json.Decode.decodeString successDecoder body of
                    Ok res ->
                        Result.Ok res

                    Err _ ->
                        Result.Err (BadBody metadata body)
            )
        )


expectJsonCustom :
    Dict.Dict String (Json.Decode.Decoder err)
    -> Json.Decode.Decoder success
    -> (Result (Error err String) success -> msg)
    -> Http.Expect msg
expectJsonCustom errorDecoders successDecoder toMsg =
    Http.expectStringResponse
        toMsg
        (responseToResult
            errorDecoders
            Basics.identity
            (\metadata body ->
                case Json.Decode.decodeString successDecoder body of
                    Ok res ->
                        Result.Ok res

                    Err _ ->
                        Result.Err (BadBody metadata body)
            )
        )
