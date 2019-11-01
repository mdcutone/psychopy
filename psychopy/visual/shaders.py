#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Part of the PsychoPy library
# Copyright (C) 2002-2018 Jonathan Peirce (C) 2019 Open Science Tools Ltd.
# Distributed under the terms of the GNU General Public License (GPL).

"""shaders programs for either pyglet or pygame
"""

from __future__ import absolute_import, print_function

import pyglet.gl as GL
import psychopy.tools.gltools as gltools


def compileProgram(vertexSource=None, fragmentSource=None):
    """Create and compile a vertex and fragment shader pair from their sources.

    Parameters
    ----------
    vertexSource, fragmentSource : str or list of str
        Vertex and fragment shader GLSL sources.

    Returns
    -------
    int
        Program object handle.

    """
    program = gltools.createProgramObjectARB()

    vertexShader = fragmentShader = None
    if vertexSource:
        vertexShader = gltools.compileShaderObjectARB(
            vertexSource, GL.GL_VERTEX_SHADER_ARB)
        gltools.attachObjectARB(program, vertexShader)
    if fragmentSource:
        fragmentShader = gltools.compileShaderObjectARB(
            fragmentSource, GL.GL_FRAGMENT_SHADER_ARB)
        gltools.attachObjectARB(program, fragmentShader)

    gltools.linkProgramObjectARB(program)
    # gltools.validateProgramARB(program)

    if vertexShader:
        gltools.detachObjectARB(program, vertexShader)
        gltools.deleteObjectARB(vertexShader)
    if fragmentShader:
        gltools.detachObjectARB(program, fragmentShader)
        gltools.deleteObjectARB(fragmentShader)

    return program


"""NOTE about frag shaders using FBO. If a floating point texture is being
used as a frame buffer (FBO object) then we should keep in the range -1:1
during frag shader. Otherwise we need to convert to 0:1. This means that
some shaders differ for FBO use if they're performing any signed math.
"""

fragFBOtoFrame = '''
    uniform sampler2D texture;

    float rand(vec2 seed){
        return fract(sin(dot(seed.xy ,vec2(12.9898,78.233))) * 43758.5453);
    }

    void main() {
        vec4 textureFrag = texture2D(texture,gl_TexCoord[0].st);
        gl_FragColor.rgb = textureFrag.rgb;
        //! if too high then show red/black noise
        if ( gl_FragColor.r>1.0 || gl_FragColor.g>1.0 || gl_FragColor.b>1.0) {
            gl_FragColor.rgb = vec3 (rand(gl_TexCoord[0].st), 0, 0);
        }
        //! if too low then show red/black noise
        else if ( gl_FragColor.r<0.0 || gl_FragColor.g<0.0 || gl_FragColor.b<0.0) {
            gl_FragColor.rgb = vec3 (0, 0, rand(gl_TexCoord[0].st));
        }
    }
    '''

# for stimuli with no texture (e.g. shapes)
fragSignedColor = '''
    void main() {
        gl_FragColor.rgb = ((gl_Color.rgb*2.0-1.0)+1.0)/2.0;
        gl_FragColor.a = gl_Color.a;
    }
    '''
fragSignedColor_adding = '''
    void main() {
        gl_FragColor.rgb = (gl_Color.rgb*2.0-1.0)/2.0;
        gl_FragColor.a = gl_Color.a;
    }
    '''
# for stimuli with just a colored texture
fragSignedColorTex = '''
    uniform sampler2D texture;
    void main() {
        vec4 textureFrag = texture2D(texture,gl_TexCoord[0].st);
        gl_FragColor.rgb = (textureFrag.rgb* (gl_Color.rgb*2.0-1.0)+1.0)/2.0;
        gl_FragColor.a = gl_Color.a*textureFrag.a;
    }
    '''
fragSignedColorTex_adding = '''
    uniform sampler2D texture;
    void main() {
        vec4 textureFrag = texture2D(texture,gl_TexCoord[0].st);
        gl_FragColor.rgb = textureFrag.rgb * (gl_Color.rgb*2.0-1.0)/2.0;
        gl_FragColor.a = gl_Color.a * textureFrag.a;
    }
    '''
# the shader for pyglet fonts doesn't use multitextures - just one texture
fragSignedColorTexFont = '''
    uniform sampler2D texture;
    uniform vec3 rgb;
    void main() {
        vec4 textureFrag = texture2D(texture,gl_TexCoord[0].st);
        gl_FragColor.rgb=rgb;
        gl_FragColor.a = gl_Color.a*textureFrag.a;
    }
    '''
# for stimuli with a colored texture and a mask (gratings, etc.)
fragSignedColorTexMask = '''
    uniform sampler2D texture, mask;
    void main() {
        vec4 textureFrag = texture2D(texture,gl_TexCoord[0].st);
        vec4 maskFrag = texture2D(mask,gl_TexCoord[1].st);
        gl_FragColor.a = gl_Color.a*maskFrag.a*textureFrag.a;
        gl_FragColor.rgb = (textureFrag.rgb* (gl_Color.rgb*2.0-1.0)+1.0)/2.0;
    }
    '''
fragSignedColorTexMask_adding = '''
    uniform sampler2D texture, mask;
    void main() {
        vec4 textureFrag = texture2D(texture,gl_TexCoord[0].st);
        vec4 maskFrag = texture2D(mask,gl_TexCoord[1].st);
        gl_FragColor.a = gl_Color.a * maskFrag.a * textureFrag.a;
        gl_FragColor.rgb = textureFrag.rgb * (gl_Color.rgb*2.0-1.0)/2.0;
    }
    '''
# RadialStim uses a 1D mask with a 2D texture
fragSignedColorTexMask1D = '''
    uniform sampler2D texture;
    uniform sampler1D mask;
    void main() {
        vec4 textureFrag = texture2D(texture,gl_TexCoord[0].st);
        vec4 maskFrag = texture1D(mask,gl_TexCoord[1].s);
        gl_FragColor.a = gl_Color.a*maskFrag.a*textureFrag.a;
        gl_FragColor.rgb = (textureFrag.rgb* (gl_Color.rgb*2.0-1.0)+1.0)/2.0;
    }
    '''
fragSignedColorTexMask1D_adding = '''
    uniform sampler2D texture;
    uniform sampler1D mask;
    void main() {
        vec4 textureFrag = texture2D(texture,gl_TexCoord[0].st);
        vec4 maskFrag = texture1D(mask,gl_TexCoord[1].s);
        gl_FragColor.a = gl_Color.a * maskFrag.a*textureFrag.a;
        gl_FragColor.rgb = textureFrag.rgb * (gl_Color.rgb*2.0-1.0)/2.0;
    }
    '''
# imageStim is providing its texture unsigned
fragImageStim = '''
    uniform sampler2D texture;
    uniform sampler2D mask;
    void main() {
        vec4 textureFrag = texture2D(texture,gl_TexCoord[0].st);
        vec4 maskFrag = texture2D(mask,gl_TexCoord[1].st);
        gl_FragColor.a = gl_Color.a*maskFrag.a*textureFrag.a;
        gl_FragColor.rgb = ((textureFrag.rgb*2.0-1.0)*(gl_Color.rgb*2.0-1.0)+1.0)/2.0;
    }
    '''
# imageStim is providing its texture unsigned
fragImageStim_adding = '''
    uniform sampler2D texture;
    uniform sampler2D mask;
    void main() {
        vec4 textureFrag = texture2D(texture,gl_TexCoord[0].st);
        vec4 maskFrag = texture2D(mask,gl_TexCoord[1].st);
        gl_FragColor.a = gl_Color.a*maskFrag.a*textureFrag.a;
        gl_FragColor.rgb = (textureFrag.rgb*2.0-1.0)*(gl_Color.rgb*2.0-1.0)/2.0;
    }
    '''
# in every case our vertex shader is simple (we don't transform coords)
vertSimple = """
    void main() {
            gl_FrontColor = gl_Color;
            gl_TexCoord[0] = gl_MultiTexCoord0;
            gl_TexCoord[1] = gl_MultiTexCoord1;
            gl_TexCoord[2] = gl_MultiTexCoord2;
            gl_Position =  ftransform();
    }
    """

vertPhongLighting = """
// Vertex shader for the Phong Shading Model
// 
// This code is based of the tutorial here:
//     https://www.opengl.org/sdk/docs/tutorials/ClockworkCoders/lighting.php
//
// Only supports directional and point light sources for now. Spotlights will be
// added later on.
//
#version 120
varying vec3 N;
varying vec3 v;
varying vec4 frontColor;
varying vec4 ShadowCoord;
varying vec3 fragPos;

uniform mat4 modelMatrix;
uniform mat4 viewMatrix;
uniform mat4 projectionMatrix;
uniform mat4 lightSpaceMatrix;

void main(void)  
{     
    v = vec3(viewMatrix * modelMatrix * gl_Vertex);       
    N = normalize(transpose(mat3(modelMatrix)) * gl_Normal);
    
    mat4 bias = mat4(0.5, 0.0, 0.0, 0.0,
                    0.0, 0.5, 0.0, 0.0,
                    0.0, 0.0, 0.5, 0.0,
                    0.5, 0.5, 0.5, 1.0);
    
    gl_TexCoord[0] = gl_MultiTexCoord0;
    gl_Position =  projectionMatrix * viewMatrix * modelMatrix * gl_Vertex;
    ShadowCoord = (bias * lightSpaceMatrix) * gl_Vertex;
    frontColor = gl_Color;
}
          
"""

fragPhongLighting = """
// Fragment shader for the Phong Shading Model
// 
// This code is based of the tutorial here:
//     https://www.opengl.org/sdk/docs/tutorials/ClockworkCoders/lighting.php
//
// Use `embedShaderSourceDefs` from gltools to enable the code path for diffuse 
// texture maps by setting DIFFUSE to 1. The number of lights can be specified 
// by setting MAX_LIGHTS, by default, the maximum should be 8. However, build
// your shader for the exact number of lights required. 
//
// Only supports directional and point light sources for now. Spotlights will be
// added later on.
//
#version 120

struct Material {
    vec4 ambient;
    vec4 diffuse;
    vec4 specular;
    float shininess;
}; 
  
uniform Material material;

struct Light {
    vec4 position;
    vec4 ambient;
    vec4 diffuse;
    vec4 specular;
    vec3 attenuation;
};

#if MAX_LIGHTS > 0
uniform Light sceneLights[MAX_LIGHTS];
#else
uniform Light sceneLights;
#endif

uniform vec3 sceneAmbient;

varying vec3 N;
varying vec3 v; 
varying vec4 frontColor;
varying vec4 ShadowCoord;
varying vec4 fragPos;

vec2 poissonDisk[16] = vec2[]( 
   vec2( -0.94201624, -0.39906216 ), 
   vec2( 0.94558609, -0.76890725 ), 
   vec2( -0.094184101, -0.92938870 ), 
   vec2( 0.34495938, 0.29387760 ), 
   vec2( -0.91588581, 0.45771432 ), 
   vec2( -0.81544232, -0.87912464 ), 
   vec2( -0.38277543, 0.27676845 ), 
   vec2( 0.97484398, 0.75648379 ), 
   vec2( 0.44323325, -0.97511554 ), 
   vec2( 0.53742981, -0.47373420 ), 
   vec2( -0.26496911, -0.41893023 ), 
   vec2( 0.79197514, 0.19090188 ), 
   vec2( -0.24188840, 0.99706507 ), 
   vec2( -0.81409955, 0.91437590 ), 
   vec2( 0.19984126, 0.78641367 ), 
   vec2( 0.14383161, -0.14100790 ) 
);

#ifdef DIFFUSE_TEXTURE
    uniform sampler2D diffTexture;
#endif
uniform sampler2D shadowMap;

// Calculate lighting attenuation using the same formula OpenGL uses
float calcAttenuation(float kConst, float kLinear, float kQuad, float dist) {
    return 1.0 / (kConst + kLinear * dist + kQuad * dist * dist);
}

void main (void)  
{  
#ifdef DIFFUSE_TEXTURE
    vec4 diffTexColor = texture2D(diffTexture, gl_TexCoord[0].st);
#endif 

#if MAX_LIGHTS > 0
    vec3 N = normalize(N);
    vec4 finalColor = vec4(0.0);
    // loop over available lights
    for (int i=0; i < MAX_LIGHTS; i++)
    {
        vec3 L;
        float attenuation = 1.0;  // default factor, no attenuation
        
        // check if directional, compute attenuation if a point source
        if (sceneLights[i].position.w == 0.0) 
        {
            // off at infinity, only use direction
            L = normalize(sceneLights[i].position.xyz);
            // attenuation is 1.0 (no attenuation for directional sources)
        } 
        else 
        {
            L = normalize(sceneLights[i].position.xyz - v);
            attenuation = calcAttenuation(
                sceneLights[i].attenuation[0],
                sceneLights[i].attenuation[1],
                sceneLights[i].attenuation[2],
                length(sceneLights[i].position.xyz - v));
        }
        
        vec3 E = normalize(-v);
        
        // combine scene ambient with object
        vec4 ambient = sceneLights[i].ambient; 
        
        // calculate diffuse component
        vec4 diffuse = material.diffuse * max(dot(N,L), 0.0);
        
#ifdef DIFFUSE_TEXTURE
        // multiply in material texture colors if specified
        diffuse *= diffTexColor;
        ambient *= diffTexColor;  // ambient should be modulated by diffuse color
#endif
        vec3 halfwayVec = normalize(L + E);  
        vec4 specular = material.specular * sceneLights[i].specular *
            pow(max(dot(N, halfwayVec), 0.0), material.shininess);
    
        // clamp color values for specular and diffuse
        ambient = clamp(ambient, 0.0, 1.0); 
        diffuse = clamp(diffuse, 0.0, 1.0); 
        specular = clamp(specular, 0.0, 1.0); 
        
        float cosTheta = clamp( dot( N, L ), 0, 1 );
        //float bias = clamp(0.005 * tan(acos(cosTheta)), 0, 0.01);
        float bias = max(0.1 * (1.0 - dot(N, L)), 0.005);
        
        // find if a fragment is in shadow
        float shadow = 1.0;
        if ( texture2D( shadowMap, ShadowCoord.xy ).z < ShadowCoord.z - bias) {
            shadow = 0.0;
        }

        //for (int i=0;i<10;i++){
         // if ( texture2D( shadowMap, ShadowCoord.xy + poissonDisk[i]/700.0 ).z  <  ShadowCoord.z-bias ){
        //    shadow -= 0.1;
         // }
       // }

        // falloff with distance from eye? might be something to consider for 
        // realism
        //vec4 emission = clamp(gl_FrontMaterial.emission, 0.0, 1.0);
        
        // finalColor += vec4(1.) * visibility;
        finalColor += ambient + shadow * (diffuse + specular);
        // finalColor += ambient + (diffuse + specular);
    }
    gl_FragColor = finalColor;  // use texture alpha
#else
    // no lights, only track ambient component, frontColor modulates ambient
    vec4 ambient = vec4(sceneAmbient, 1.0); 
    ambient = clamp(ambient, 0.0, 1.0); 
//#ifdef DIFFUSE_TEXTURE
//    gl_FragColor = ambient * texture2D(diffTexture, gl_TexCoord[0].st);
//#else
    gl_FragColor = ambient;
#endif
}
"""

# render only a depth map
vertDepthMap = """
#version 110

uniform mat4 modelMatrix;
uniform mat4 lightMatrix;

void main() {
    gl_Position = lightMatrix * gl_Vertex;
}  

"""

# pass-through fragment shader for vertex shader only operations
fragNull = """
void main() {
    gl_FragDepth = gl_FragCoord.z;
}
"""

fragDepthToTexture = """
uniform sampler2D depthMap;

void main()
{             
    float depthValue = texture2D(depthMap, gl_TexCoord[0].st).r;
    gl_FragColor = vec4(vec3(depthValue), 1.0);
}  
"""